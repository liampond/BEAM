
"""
CLI and orchestration for running the LLM benchmark.

Usage (from repository root):
    python src/run_benchmark.py --model mymodel --backend mock --output results.csv --concurrency 4

This script fetches test cases from the database, extracts passages using
`extract_passage.extract`, constructs prompts, sends them to the chosen LLM
via a provider instance from `llm_integration.base`, evaluates responses using `evaluator.evaluate_response`,
and stores results in the `llm_responses` table. Results are also appended to a CSV.
"""

import argparse
import csv
import time
import json  
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any
from pathlib import Path


import extract_passage
import llm_runner
import evaluator
from llm_integration.base import get_llm_provider

def _extract_answer_from_json(response_text: str, question_key: str) -> str:
    """
    Tries to parse a JSON blob from the response and extract the answer
    based on the question_key (e.g., 'key', 'pitch', 'time').
    """
    try:
        # Regex to find the first valid-looking JSON object
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            json_data = json.loads(json_match.group(0))
            
            # Use the question_key to find the answer
            if question_key in json_data:
                return str(json_data[question_key])
            
            # Fallback: if only one key, return its value
            if len(json_data) == 1:
                return str(list(json_data.values())[0])
                
    except (json.JSONDecodeError, TypeError, IndexError):
        pass
    
    return response_text

def worker(task: Dict[str, Any], provider, timeout: int, rate_delay: float) -> Dict[str, Any]:
    """Run a single test case (task is dict from llm_runner.fetch_test_cases)."""
    test_case_id = task["test_case_id"]
    encoding_id = task["encoding_id"]
    file_path = task["file_path"]
    format = task["format"]
    start = task["start_measure"]
    end = task["end_measure"]
    question_text = task["question_text"]
    expected = task["correct_answer"]

    try:
        if start is None or end is None:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    passage = f.read()
            except Exception as e:
                passage = f"<UNREADABLE_FILE: {e}>"
        else:
            passage = extract_passage.extract(format, file_path, start, end)
    except Exception as e:
        passage = f"<EXTRACTION_ERROR: {e}>"

    prompt = llm_runner.build_prompt(question_text, passage)
    
    try:
        print(f"--- PROMPT (sending to {getattr(provider, 'model_name', 'unknown_model')} on {provider.__class__.__name__}) ---\n{prompt}\n--- END PROMPT ---")
        
        resp_text, metadata = provider.send_prompt(prompt, timeout=timeout)
        metadata = metadata or {}

        try:
            provider_name = getattr(provider, 'model_name', None) or provider.__class__.__name__
            print(f"--- MODEL RESPONSE (from {provider_name}) ---\n{resp_text}\n--- END RESPONSE ---")
        except Exception:
            print("--- MODEL RESPONSE ---")
            print(resp_text)

        question_type = task.get("question_type", "general")
        answer_value = _extract_answer_from_json(resp_text, question_type)
        is_correct, score = evaluator.evaluate_response(expected, answer_value, question_type)

    except Exception as e:
        print(f"--- API/WORKER ERROR ---\n{e}\n--- END ERROR ---")
        resp_text = f"<API_ERROR: {e}>"
        metadata = {"error": str(e)}
        is_correct = None  
        score = None

    if rate_delay:
        time.sleep(rate_delay)

    return {
        "test_case_id": test_case_id,
        "encoding_id": encoding_id,
        "model": provider.model_name,
        "backend": provider.__class__.__name__.lower().replace('provider', ''),
        "response": resp_text,
        "is_correct": is_correct,
        "score": score,
        "metadata": metadata,
    }


def run_benchmark(
    backend: str = "openai",
    api_url: Optional[str] = None,
    llm_model: Optional[str] = None,
    
    formats: Optional[List[str]] = None,
    question_id: Optional[int] = None,
    encoding_id: Optional[int] = None,
    passage_id: Optional[int] = None,
    
    timeout: int = 60,
    rate_delay: float = 0.0,
    limit: Optional[int] = None,
    concurrency: int = 2,
    
    output_csv: Optional[str] = None,
    test_file: Optional[str] = None,
):
    """
    Run benchmark tests.
    
    Minimum implementation matching example:
    1. Get passage info from database (via questions → passages → pieces join)
    2. For each format, extract content from file
    3. Send to LLM API
    4. Evaluate and store results
    
    Args:
        question_id: Specific question to run (per-question mode) or None (run all)
        llm_model: Model name/identifier
        backend: Provider backend (openai, anthropic, etc.)
        formats: List of format strings to filter by
        encoding_id: Filter to single encoding
        passage_id: Filter to single passage
        concurrency: Number of concurrent workers
        output_csv: Optional CSV output path
        timeout: API timeout in seconds
        rate_delay: Delay between API calls
        limit: Limit number of test cases
    """
    conn = llm_runner.get_connection()
    
    try:
        tasks = llm_runner.fetch_test_cases(
            conn=conn,
            question_id=question_id,
            formats=formats,
            limit=limit,
        )

        if test_file:
            if question_id is None:
                print("test_file requires --question-id to be provided")
                return []
            cur = conn.cursor()
            cur.execute("SELECT question_text FROM questions WHERE question_id = ?", (question_id,))
            row = cur.fetchone()
            if not row:
                print(f"No question found with question_id={question_id}")
                return []
            question_text = row[0]

            ext = Path(test_file).suffix.lower()
            fmt_map = {
                '.krn': 'humdrum',
                '.abc': 'abc',
                '.mei': 'mei',
                '.xml': 'musicxml',
                '.ly': 'lilypond',
            }
            fmt = fmt_map.get(ext, ext.lstrip('.') if ext else 'unknown')

            tasks = [{
                'test_case_id': 0,
                'encoding_id': None,
                'file_path': test_file,
                'format': fmt,
                'start_measure': None,
                'end_measure': None,
                'question_text': question_text,
                'correct_answer': None,
                'question_type': 'general',
                'passage_id': None,
            }]
        
        if encoding_id is not None:
            tasks = [t for t in tasks if t.get("encoding_id") == encoding_id]
        if passage_id is not None:
            tasks = [t for t in tasks if t.get("passage_id") == passage_id]
        
        if not tasks:
            print("No test cases found for the given filters.")
            return []
        
        print(f"Running {len(tasks)} test cases with model={llm_model} backend={backend} concurrency={concurrency}")
        
        results = []
        provider = get_llm_provider(backend, llm_model, timeout=timeout, api_url=api_url)
        
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = {ex.submit(worker, t, provider, timeout, rate_delay): t for t in tasks}
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    if res.get("test_case_id") != 0:
                        llm_runner.insert_llm_response(
                            conn, 
                            res["test_case_id"], 
                            res["model"], 
                            res["response"], 
                            res["is_correct"], 
                            metadata=res.get("metadata")
                        )
                    results.append(res)
                    print(f"Completed test_case_id={res['test_case_id']} (correct={res['is_correct']})")
                except Exception as e:
                    print(f"Error during test case: {e}")

        if output_csv:
            fieldnames = ["test_case_id", "encoding_id", "model", "backend", "is_correct", "score", "response"]
            with open(output_csv, "w", newline='', encoding='utf-8') as csvf:
                writer = csv.DictWriter(csvf, fieldnames=fieldnames)
                writer.writeheader()
                for r in results:
                    writer.writerow(r)
        
        print("Benchmark finished.")
        return results
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Run the LLM Music Encoding Benchmark")
    # Provider Config
    parser.add_argument("--backend", required=True, help="Backend provider (openai, anthropic, google, local)")
    parser.add_argument("--api-url", help="API URL for the 'local' backend")
    parser.add_argument("--model", required=True, help="Model label to store and (for some backends) to select")
    # Test Filters
    parser.add_argument("--format", action='append', dest='formats', help="Only run encodings with this format (repeatable)")
    parser.add_argument("--question-id", type=int, help="Only run a single question id")
    parser.add_argument("--encoding-id", type=int, help="Only run a single encoding id")
    parser.add_argument("--passage-id", type=int, help="Only run a single passage id")
    # Execution Control
    parser.add_argument("--timeout", type=int, default=60, help="API timeout in seconds")
    parser.add_argument("--rate-delay", type=float, default=0.0, help="Seconds to wait after each API call")
    parser.add_argument("--limit", type=int, help="Limit number of test cases to run")
    parser.add_argument("--concurrency", type=int, default=2, help="Number of concurrent workers")
    # Input / Output
    parser.add_argument("--output", help="CSV output file for results")
    parser.add_argument("--test-file", help="Run test file (requires --question-id)")
    
    args = parser.parse_args()
    
    run_benchmark(
        backend=args.backend,
        api_url=args.api_url,
        llm_model=args.model,
        formats=args.formats,
        question_id=args.question_id,
        encoding_id=args.encoding_id,
        passage_id=args.passage_id,
        timeout=args.timeout,
        rate_delay=args.rate_delay,
        limit=args.limit,
        concurrency=args.concurrency,
        output_csv=args.output,
        test_file=args.test_file,
    )


if __name__ == "__main__":
    main()
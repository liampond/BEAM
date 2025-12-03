#!/usr/bin/env python3
"""
Parallel Batch Submission Script

Submits batch API requests to all enabled providers in parallel,
then polls for completion. This is much faster than sequential
submission because:
    1. All batches are submitted at once
    2. Polling happens for all batches simultaneously
    3. Results are processed as each batch completes

Usage:
    python scripts/submit_all_batches.py
    python scripts/submit_all_batches.py --run-id 20251202_141834
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_eval.config import BenchmarkConfig, ModelConfig
from src.llm_eval.query import TestCaseQuery, TestCase, build_prompt
from src.llm_eval.batch import BatchRunner, BatchRequest, BatchStatus, BatchResult
from src.llm_eval.results import ResultsManager, TestResult
from src.llm_eval.providers import LLMResponse


import re


def extract_answer(response_text: str) -> str:
    """Extract answer from LLM response."""
    if not response_text:
        return ""
    
    # Try JSON extraction first
    try:
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group(0))
            for key in ['answer', 'result', 'value']:
                if key in data:
                    return str(data[key])
            # Single key fallback
            if len(data) == 1:
                return str(list(data.values())[0])
    except (json.JSONDecodeError, AttributeError):
        pass
    
    # Plain text fallback
    text = response_text.strip()
    text = re.sub(r'^(the\s+)?answer\s*(is)?:?\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def compare_answers(extracted: str, expected: str) -> bool:
    """Compare extracted answer to expected answer."""
    if not extracted or not expected:
        return False
    
    # Normalize both
    def normalize(s: str) -> str:
        s = s.strip().lower()
        # Remove common punctuation
        s = re.sub(r'[.,;:\'"!?]', '', s)
        # Collapse whitespace
        s = re.sub(r'\s+', ' ', s)
        return s
    
    e_norm = normalize(extracted)
    x_norm = normalize(expected)
    
    # Exact match
    if e_norm == x_norm:
        return True
    
    # Numeric comparison
    try:
        e_num = float(e_norm)
        x_num = float(x_norm)
        # Allow small tolerance for floating point
        return abs(e_num - x_num) < 0.01
    except ValueError:
        pass
    
    return False


def submit_single_batch(
    model_config: ModelConfig,
    batch_requests: List[BatchRequest],
    config: BenchmarkConfig,
    results_manager: ResultsManager,
    run_number: int = 1,
) -> Tuple[str, str, str, int]:
    """
    Submit a single batch for a model.
    
    Returns:
        Tuple of (model_name, batch_id, provider, run_number)
    """
    # Use model-specific temperature or fallback to config default
    temperature = model_config.temperature if model_config.temperature is not None else config.api_settings.temperature
    
    batch_runner = BatchRunner(
        provider=model_config.provider,
        model_name=model_config.name,
        max_tokens=model_config.max_tokens or config.api_settings.max_tokens,
        temperature=temperature,
    )
    
    batch_id = batch_runner.submit(
        batch_requests,
        json_mode=config.prompt.enforce_json,
    )
    
    # Save batch ID with run number
    batch_key = f"{model_config.name}_run{run_number}"
    save_batch_id_extended(results_manager, model_config, batch_id, run_number)
    
    return (model_config.name, batch_id, model_config.provider, run_number)


def save_batch_id_extended(
    results_manager: ResultsManager,
    model_config: ModelConfig,
    batch_id: str,
    run_number: int,
):
    """Save batch ID with run number for resumption."""
    batch_ids_path = results_manager.output_dir / "batch_ids.json"
    
    # Load existing
    if batch_ids_path.exists():
        with open(batch_ids_path) as f:
            batch_ids = json.load(f)
    else:
        batch_ids = {}
    
    # Key with run number
    key = f"{model_config.name}_run{run_number}"
    batch_ids[key] = {
        "batch_id": batch_id,
        "provider": model_config.provider,
        "model_name": model_config.name,
        "run_number": run_number,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Save
    with open(batch_ids_path, 'w') as f:
        json.dump(batch_ids, f, indent=2)


def poll_batch_status(
    key: str,
    batch_id: str,
    provider: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, BatchStatus]:
    """
    Check status of a single batch.
    
    Returns:
        Tuple of (key, BatchStatus)
    """
    batch_runner = BatchRunner(
        provider=provider,
        model_name=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    
    status = batch_runner.get_status(batch_id)
    return (key, status)


def retrieve_batch_results(
    key: str,
    batch_id: str,
    provider: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, List[BatchResult]]:
    """
    Retrieve results for a completed batch.
    
    Returns:
        Tuple of (key, results)
    """
    batch_runner = BatchRunner(
        provider=provider,
        model_name=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    
    results = batch_runner.get_results(batch_id)
    return (key, results)


def process_batch_results(
    batch_results: List[BatchResult],
    test_case_map: Dict[str, TestCase],
    model_config: ModelConfig,
    run_number: int,
    system_prompt: str,
    config: BenchmarkConfig,
    results_manager: ResultsManager,
) -> List[TestResult]:
    """Process batch results into TestResults and save them."""
    results = []
    
    for batch_result in batch_results:
        test_case = test_case_map.get(batch_result.custom_id)
        if not test_case:
            continue
        
        # Create LLMResponse from batch result
        response = LLMResponse(
            text=batch_result.response_text,
            model=model_config.name,
            provider=model_config.provider,
            success=batch_result.success,
            error=batch_result.error,
            raw_metadata=batch_result.metadata,
        )
        response.extract_json_answer()
        
        # Extract and evaluate the answer
        extracted = extract_answer(response.parsed_answer if response.parsed_answer else response.text)
        is_correct = compare_answers(extracted, test_case.expected_answer)
        
        # Build prompt for result storage
        prompt = build_prompt(
            test_case,
            system_prompt,
            include_format_hint=config.prompt.include_format_hint,
        )
        
        result = TestResult(
            question_id=test_case.question_id,
            passage_id=test_case.passage_id,
            format=test_case.format,
            model_name=model_config.name,
            provider=model_config.provider,
            run_number=run_number,
            question_text=test_case.question_text,
            expected_answer=test_case.expected_answer,
            extracted_answer=extracted,
            raw_response=response.text,
            is_correct=is_correct,
            success=response.success,
            error=response.error,
            timestamp=datetime.now().isoformat(),
            prompt=prompt,
        )
        results.append(result)
        
        # Save immediately
        results_manager.save_single_result(model_config, result)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Submit batch API requests in parallel"
    )
    parser.add_argument(
        "--run-id",
        help="Existing run ID to continue (use existing batch_ids.json)",
    )
    parser.add_argument(
        "--poll-only",
        action="store_true",
        help="Only poll existing batches, don't submit new ones",
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=60,
        help="Seconds between status checks (default: 60)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=None,
        help="Number of runs per model (overrides config)",
    )
    args = parser.parse_args()
    
    # Load configuration
    config_path = Path(__file__).parent.parent / "config.yaml"
    config = BenchmarkConfig.from_yaml(config_path)
    config.load_api_keys()
    
    # Set up run ID
    if args.run_id:
        config.output.resume_run_id = args.run_id
        run_id = args.run_id
    else:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Override runs if specified
    runs_per_question = args.runs if args.runs else config.execution.runs_per_question
    
    # Create results manager
    results_manager = ResultsManager(config)
    output_dir = results_manager.output_dir
    print(f"Output directory: {output_dir}")
    
    # Get enabled models
    enabled_models = config.get_enabled_models()
    print(f"\nEnabled models: {[m.name for m in enabled_models]}")
    print(f"Runs per question: {runs_per_question}")
    
    # Load existing batch IDs if resuming
    batch_ids_path = output_dir / "batch_ids.json"
    existing_batches = {}
    if batch_ids_path.exists():
        with open(batch_ids_path) as f:
            existing_batches = json.load(f)
        print(f"Found existing batches: {list(existing_batches.keys())}")
    
    # Load system prompt and test cases
    system_prompt = config.get_system_prompt()
    query = TestCaseQuery(config)
    
    # Fetch test cases
    print("\nFetching test cases...")
    test_cases = query.fetch_test_cases()
    print(f"Found {len(test_cases)} test cases")
    
    if not test_cases:
        print("No test cases match filter criteria")
        return
    
    # Show summary
    summary = query.get_summary()
    print(f"  By format: {summary['by_format']}")
    
    # Create test case map for result processing
    test_case_map = {tc.custom_id: tc for tc in test_cases}
    
    if not args.poll_only:
        # Prepare batch requests (same for all models/runs)
        print("\nPreparing batch requests...")
        batch_requests = []
        for test_case in test_cases:
            prompt = build_prompt(
                test_case,
                system_prompt,
                include_format_hint=config.prompt.include_format_hint,
            )
            batch_requests.append(BatchRequest(
                custom_id=test_case.custom_id,
                prompt=prompt,
                system_prompt=system_prompt,
                metadata={"test_case": test_case},
            ))
        print(f"Prepared {len(batch_requests)} requests per batch")
        
        # Figure out which batches to submit (model + run_number combinations)
        batches_to_submit = []
        for model in enabled_models:
            for run_num in range(1, runs_per_question + 1):
                key = f"{model.name}_run{run_num}"
                if key not in existing_batches:
                    batches_to_submit.append((model, run_num))
                else:
                    print(f"  Skipping {key}: already has batch {existing_batches[key]['batch_id'][:20]}...")
        
        if batches_to_submit:
            total_batches = len(batches_to_submit)
            total_requests = total_batches * len(batch_requests)
            print(f"\nSubmitting {total_batches} batches ({total_requests:,} total requests)")
            
            # Submit in parallel (but limit concurrency to avoid overwhelming APIs)
            max_workers = min(len(batches_to_submit), 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        submit_single_batch,
                        model,
                        batch_requests,
                        config,
                        results_manager,
                        run_num,
                    ): (model, run_num)
                    for model, run_num in batches_to_submit
                }
                
                for future in as_completed(futures):
                    model, run_num = futures[future]
                    try:
                        model_name, batch_id, provider, _ = future.result()
                        key = f"{model_name}_run{run_num}"
                        print(f"  ✓ {key}: {batch_id[:30]}...")
                        existing_batches[key] = {
                            "batch_id": batch_id,
                            "provider": provider,
                            "model_name": model_name,
                            "run_number": run_num,
                        }
                    except Exception as e:
                        print(f"  ✗ {model.name}_run{run_num}: {e}")
    
    # Now poll all batches until complete
    if not existing_batches:
        print("\nNo batches to poll")
        return
    
    print(f"\nPolling {len(existing_batches)} batches...")
    print(f"Check interval: {args.check_interval} seconds")
    
    # Track completion
    completed = set()
    all_results: Dict[str, List[TestResult]] = {}
    
    while len(completed) < len(existing_batches):
        pending = {k: v for k, v in existing_batches.items() if k not in completed}
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking {len(pending)} pending batches...")
        
        # Check all pending batches in parallel
        with ThreadPoolExecutor(max_workers=min(len(pending), 4)) as executor:
            futures = {}
            for key, batch_info in pending.items():
                model_name = batch_info.get("model_name", key.rsplit("_run", 1)[0])
                
                # Find model config
                model_config = next((m for m in enabled_models if m.name == model_name), None)
                if not model_config:
                    print(f"  Warning: No config for {model_name}")
                    completed.add(key)
                    continue
                
                temperature = model_config.temperature if model_config.temperature is not None else config.api_settings.temperature
                
                futures[executor.submit(
                    poll_batch_status,
                    key,
                    batch_info["batch_id"],
                    batch_info["provider"],
                    model_name,
                    temperature,
                    model_config.max_tokens or config.api_settings.max_tokens,
                )] = key
            
            for future in as_completed(futures):
                key = futures[future]
                try:
                    _, status = future.result()
                    status_str = f"{status.status} ({status.progress_pct:.1f}%)"
                    
                    if status.is_complete:
                        completed.add(key)
                        batch_info = existing_batches[key]
                        model_name = batch_info.get("model_name", key.rsplit("_run", 1)[0])
                        run_number = batch_info.get("run_number", 1)
                        
                        if status.status == "completed":
                            print(f"  {key}: COMPLETED - Retrieving results...")
                            
                            # Retrieve results
                            model_config = next(m for m in enabled_models if m.name == model_name)
                            temperature = model_config.temperature if model_config.temperature is not None else config.api_settings.temperature
                            
                            _, batch_results = retrieve_batch_results(
                                key,
                                batch_info["batch_id"],
                                batch_info["provider"],
                                model_name,
                                temperature,
                                model_config.max_tokens or config.api_settings.max_tokens,
                            )
                            
                            # Process and save results
                            test_results = process_batch_results(
                                batch_results,
                                test_case_map,
                                model_config,
                                run_number,
                                system_prompt,
                                config,
                                results_manager,
                            )
                            
                            all_results[key] = test_results
                            success = sum(1 for r in test_results if r.is_correct)
                            print(f"    → Saved {len(test_results)} results ({success} correct)")
                        else:
                            print(f"  {key}: {status.status}")
                    else:
                        print(f"  {key}: {status_str}")
                            
                except Exception as e:
                    print(f"  {key}: Error - {e}")
                    import traceback
                    traceback.print_exc()
        
        if len(completed) < len(existing_batches):
            print(f"Waiting {args.check_interval} seconds...")
            time.sleep(args.check_interval)
    
    print(f"\n{'='*60}")
    print("All batches complete!")
    print(f"{'='*60}")
    
    # Summary
    total_correct = 0
    total_tests = 0
    for key, results in all_results.items():
        success = sum(1 for r in results if r.is_correct)
        total_correct += success
        total_tests += len(results)
        print(f"  {key}: {success}/{len(results)} correct ({100*success/len(results):.1f}%)")
    
    if total_tests > 0:
        print(f"\nOverall: {total_correct}/{total_tests} correct ({100*total_correct/total_tests:.1f}%)")
    
    print(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    main()

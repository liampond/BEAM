#!/usr/bin/env python3
"""
Run LLM benchmark tests based on config.yaml

This script:
1. Loads configuration from config.yaml
2. Loads API keys from .env
3. Fetches questions and test cases from database
4. Sends prompts to configured LLM providers
5. Saves responses in outputs/{model}/{question}/ structure
6. Evaluates responses against ground truth
7. Saves results to database and files

Usage:
    # Run with all enabled models from config (default)
    python src/cli/run_benchmark.py
    
    # Run specific questions with all enabled models
    python src/cli/run_benchmark.py --questions 22 23 24
    
    # Run all questions with all enabled models
    python src/cli/run_benchmark.py --all
    
    # Test only specific models (overrides config)
    python src/cli/run_benchmark.py --questions 22 --models qwen3-max claude-sonnet-4-5
    
    # Use custom config
    python src/cli/run_benchmark.py --config my_config.yaml
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import yaml
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
import os
import re
from dotenv import load_dotenv

from core import extract_passage
from core.db_utils import get_connection
from llm_eval.providers import get_provider as get_llm_provider


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def load_api_keys():
    """Load API keys from .env file."""
    load_dotenv()
    
    keys = {
        'ANTHROPIC_API_KEY': os.getenv('CLAUDE_API_KEY'),      # .env uses CLAUDE_API_KEY
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'GOOGLE_API_KEY': os.getenv('GEMINI_API_KEY'),         # .env uses GEMINI_API_KEY
        'DASHSCOPE_API_KEY': os.getenv('DASHSCOPE_API_KEY'),   # Alibaba Cloud / Qwen
    }
    
    # Set them in environment for the libraries to use
    for key, value in keys.items():
        if value:
            os.environ[key] = value
    
    return keys


def get_enabled_models(config: Dict[str, Any]) -> List[Dict[str, str]]:
    """Get list of enabled models from config."""
    return [m for m in config['models'] if m.get('enabled', True)]


def fetch_test_cases(question_ids: Optional[List[int]] = None, 
                    formats: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Fetch test cases from database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Build query
    query = """
        SELECT 
            tc.test_case_id,
            tc.question_id,
            q.question_text,
            CASE e.format
                WHEN 'musicxml' THEN q.answer_musicxml
                WHEN 'abc' THEN q.answer_abc
                WHEN 'mei' THEN q.answer_mei
                WHEN 'humdrum' THEN q.answer_humdrum
                ELSE q.answer_humdrum
            END AS correct_answer,
            q.question_type,
            tc.encoding_id,
            e.format,
            e.file_path,
            p.passage_id,
            p.start_measure,
            p.end_measure,
            p.piece_id,
            CASE e.format
                WHEN 'musicxml' THEN q.verified_musicxml
                WHEN 'abc' THEN q.verified_abc
                WHEN 'mei' THEN q.verified_mei
                WHEN 'humdrum' THEN q.verified_humdrum
                ELSE 0
            END AS verified_answer
        FROM test_cases tc
        JOIN questions q ON tc.question_id = q.question_id
        JOIN encodings e ON tc.encoding_id = e.encoding_id
        JOIN passages p ON q.passage_id = p.passage_id
        WHERE 1=1
    """
    
    params = []
    if question_ids:
        placeholders = ','.join('?' * len(question_ids))
        query += f" AND tc.question_id IN ({placeholders})"
        params.extend(question_ids)
    
    if formats:
        placeholders = ','.join('?' * len(formats))
        query += f" AND e.format IN ({placeholders})"
        params.extend(formats)
    
    query += " ORDER BY tc.question_id, e.format"
    
    cursor.execute(query, params)
    
    columns = [desc[0] for desc in cursor.description]
    test_cases = []
    for row in cursor.fetchall():
        test_cases.append(dict(zip(columns, row)))
    
    conn.close()
    return test_cases


def extract_answer_from_response(response_text: str, question_type: Optional[str] = None) -> str:
    """Extract answer from LLM response (handles JSON or plain text)."""
    # Try to parse as JSON first
    try:
        # Look for JSON object in response
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group(0))
            # Try common answer keys
            for key in ['answer', 'result', 'value', 'count', 'number']:
                if key in data:
                    return str(data[key])
            # If only one key, return its value
            if len(data) == 1:
                return str(list(data.values())[0])
    except (json.JSONDecodeError, AttributeError):
        pass
    
    # Fall back to plain text (strip whitespace and common wrappers)
    answer = response_text.strip()
    # Remove common wrappers like "The answer is: X" or "Answer: X"
    answer = re.sub(r'^(the\s+)?answer\s*(is)?:?\s*', '', answer, flags=re.IGNORECASE)
    return answer.strip()


def evaluate_response(expected: str, extracted: str, question_type: Optional[str] = None) -> tuple:
    """Simple evaluation: compare expected and extracted answers.
    
    Returns:
        (is_correct, score) tuple
    """
    # Normalize both answers
    expected_norm = str(expected).strip().lower()
    extracted_norm = str(extracted).strip().lower()
    
    is_correct = expected_norm == extracted_norm
    score = 1.0 if is_correct else 0.0
    
    return is_correct, score


def save_response(response_data: Dict[str, Any], config: Dict[str, Any]):
    """Save response to file system."""
    output_config = config['output']
    base_dir = Path(output_config['base_dir'])
    
    # Create directory structure: outputs/{model}/{question}/
    model_name = response_data['model_name'].replace('/', '_')  # Handle slashes in model names
    question_id = f"Q-{response_data['question_id']:03d}"
    
    output_dir = base_dir / model_name / question_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    format_name = response_data['format']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save full response as JSON
    if output_config.get('save_responses', True):
        response_file = output_dir / f"{format_name}_response_{timestamp}.json"
        with open(response_file, 'w') as f:
            json.dump(response_data, f, indent=2)
    
    return output_dir


def save_to_database(response_data: Dict[str, Any]):
    """Save response to llm_responses table."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO llm_responses 
        (test_case_id, llm_model, llm_response, is_correct, response_time, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        response_data['test_case_id'],
        response_data['model_name'],
        response_data['raw_response'],
        response_data['is_correct'],
        response_data['duration_seconds'],
        response_data['timestamp']
    ))
    
    conn.commit()
    conn.close()


def run_single_test(test_case: Dict[str, Any], 
                   model_config: Dict[str, str],
                   config: Dict[str, Any],
                   system_prompt: str) -> Dict[str, Any]:
    """Run a single test case with a specific model."""
    
    # Extract passage
    format_name = test_case['format']
    file_path = test_case['file_path']
    start_measure = test_case['start_measure']
    end_measure = test_case['end_measure']
    
    try:
        passage_text = extract_passage.extract(format_name, file_path, start_measure, end_measure)
    except Exception as e:
        passage_text = f"<EXTRACTION_ERROR: {e}>"
    
    # Build prompt
    prompt_config = config['prompt']
    question_text = test_case['question_text']
    
    if prompt_config.get('include_format_hint', True):
        format_hint = f"\n[Note: This is {format_name.upper()} format]"
        question_with_hint = question_text + format_hint
    else:
        question_with_hint = question_text
    
    # Construct full prompt with system message
    prompt = (
        f"{system_prompt}\n\n"
        f"Passage:\n{passage_text}\n\n"
        f"Question: {question_with_hint}\n\n"
    )
    
    # Get LLM provider
    api_settings = config['api_settings']
    provider = get_llm_provider(
        provider=model_config['provider'],
        model_name=model_config['name'],
        temperature=api_settings['temperature'],
        seed=api_settings['seed'],
        max_tokens=api_settings['max_tokens'],
        timeout=api_settings['timeout']
    )
    
    # Send prompt
    start_time = datetime.now()
    try:
        response_text, metadata = provider.send_prompt(prompt)
        success = True
        error = None
    except Exception as e:
        response_text = ""
        metadata = {}
        success = False
        error = str(e)
    
    end_time = datetime.now()
    
    # Extract answer
    extracted_answer = extract_answer_from_response(response_text, test_case['question_type'])
    
    # Evaluate
    expected_answer = test_case['correct_answer']
    is_correct, score = evaluate_response(
        expected_answer, 
        extracted_answer,
        question_type=test_case['question_type']
    )
    eval_details = {'method': 'auto'}
    
    # Prepare response data
    response_data = {
        'test_case_id': test_case['test_case_id'],
        'question_id': test_case['question_id'],
        'question_text': test_case['question_text'],
        'format': format_name,
        'model_name': model_config['name'],
        'provider': model_config['provider'],
        'prompt': prompt if config['output'].get('save_prompts', True) else None,
        'raw_response': response_text,
        'extracted_answer': extracted_answer,
        'expected_answer': expected_answer,
        'is_correct': is_correct,
        'score': score,
        'evaluation_method': eval_details.get('method', 'exact'),
        'evaluation_details': eval_details,
        'metadata': metadata,
        'success': success,
        'error': error,
        'timestamp': start_time.isoformat(),
        'duration_seconds': (end_time - start_time).total_seconds()
    }
    
    return response_data


def main():
    parser = argparse.ArgumentParser(description='Run LLM benchmark tests')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--questions', nargs='+', type=int, help='Specific question IDs to test')
    parser.add_argument('--all', action='store_true', help='Test all questions')
    parser.add_argument('--models', nargs='+', help='Specific models to test (by name)')
    args = parser.parse_args()
    
    # Load configuration
    print(f"Loading configuration from {args.config}...")
    config = load_config(args.config)
    
    # Load system prompt from file
    system_prompt_file = config['prompt'].get('system_prompt_file', 'prompts/system_prompt.txt')
    print(f"Loading system prompt from {system_prompt_file}...")
    with open(system_prompt_file, 'r') as f:
        system_prompt = f.read().strip()
    
    # Load API keys
    print("Loading API keys from .env...")
    api_keys = load_api_keys()
    
    # Determine which questions to test
    if args.all:
        question_ids = None  # Will fetch all
        print("Testing all questions")
    elif args.questions:
        question_ids = args.questions
        print(f"Testing questions: {question_ids}")
    else:
        # Use config
        if config['execution']['mode'] == 'all':
            question_ids = None
            print("Testing all questions (from config)")
        else:
            question_ids = config['execution']['questions']
            print(f"Testing questions from config: {question_ids}")
    
    # Get enabled models
    enabled_models = get_enabled_models(config)
    if args.models:
        # Filter to only requested models
        enabled_models = [m for m in enabled_models if m['name'] in args.models]
    
    print(f"\nEnabled models: {[m['name'] for m in enabled_models]}")
    
    # Fetch test cases
    print("\nFetching test cases from database...")
    test_cases = fetch_test_cases(
        question_ids=question_ids,
        formats=config['execution']['formats']
    )
    print(f"Found {len(test_cases)} test cases")
    
    # Run tests
    total_tests = len(test_cases) * len(enabled_models)
    current_test = 0
    
    results = []
    
    for model_config in enabled_models:
        print(f"\n{'='*80}")
        print(f"Testing with {model_config['provider']}/{model_config['name']}")
        print(f"{'='*80}")
        
        for test_case in test_cases:
            current_test += 1
            q_id = test_case['question_id']
            fmt = test_case['format']
            
            print(f"\n[{current_test}/{total_tests}] Q-{q_id:03d} ({fmt})...", end=' ')
            
            try:
                response_data = run_single_test(test_case, model_config, config, system_prompt)
                
                # Save response
                if config['output'].get('save_responses', True):
                    save_response(response_data, config)
                
                # Save to database
                if config['output'].get('save_to_database', True):
                    save_to_database(response_data)
                
                results.append(response_data)
                
                # Print result
                if response_data['success']:
                    status = "✓" if response_data['is_correct'] else "✗"
                    print(f"{status} {response_data['extracted_answer']} (expected: {response_data['expected_answer']})")
                else:
                    print(f"ERROR: {response_data['error']}")
                
            except Exception as e:
                print(f"FAILED: {e}")
                import traceback
                traceback.print_exc()
            
            # Rate limiting
            import time
            time.sleep(config['api_settings']['rate_limit_delay'])
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    successful = [r for r in results if r['success']]
    correct = [r for r in results if r['is_correct']]
    
    print(f"Total tests: {len(results)}")
    if len(results) > 0:
        print(f"Successful: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
        print(f"Correct: {len(correct)} ({len(correct)/len(results)*100:.1f}%)")
    else:
        print("No tests were run!")
    
    # Save summary
    if len(results) > 0:
        summary_file = Path(config['output']['base_dir']) / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w') as f:
            json.dump({
                'config': config,
                'total_tests': len(results),
                'successful': len(successful),
                'correct': len(correct),
                'results': results
            }, f, indent=2)
        
        print(f"\nResults saved to: {summary_file}")
    else:
        print("\nNo results to save.")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Verify Batch Alignment Script

This script verifies that test cases are correctly aligned before batch submission.
It checks that each test case's passage_content matches the expected file content.

Run this BEFORE submitting a batch to catch misalignment issues early.

Usage:
    python scripts/verify_batch_alignment.py
    python scripts/verify_batch_alignment.py --format musicxml --num-measures 8
    python scripts/verify_batch_alignment.py --save-prompts  # Save prompts to file for inspection
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_eval.config import BenchmarkConfig
from src.llm_eval.query import TestCaseQuery, build_prompt
from src.answer_extraction.registry import get_extractor


def compute_content_fingerprint(content: str) -> dict:
    """Compute fingerprint of passage content for verification."""
    # Count key elements
    note_count = content.count('<note')
    rest_count = content.count('<rest')
    measure_matches = re.findall(r'<measure number="(\d+)"', content)
    measures = f"{measure_matches[0]}-{measure_matches[-1]}" if measure_matches else "unknown"
    
    # MD5 hash for exact matching
    content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
    
    return {
        'notes': note_count,
        'rests': rest_count,
        'measures': measures,
        'hash': content_hash,
        'length': len(content),
    }


def verify_test_case(test_case, format_name: str) -> dict:
    """
    Verify a single test case has correct passage content.
    
    Returns dict with verification results.
    """
    result = {
        'question_id': test_case.question_id,
        'passage_id': test_case.passage_id,
        'question_type_id': test_case.question_type_id,
        'expected_answer': test_case.expected_answer,
        'passed': True,
        'errors': [],
    }
    
    # Check 1: File exists
    file_path = Path(test_case.passage_file_path)
    if not file_path.exists():
        result['passed'] = False
        result['errors'].append(f"File not found: {file_path}")
        return result
    
    # Check 2: Content matches file
    file_content = file_path.read_text()
    if test_case.passage_content != file_content:
        result['passed'] = False
        result['errors'].append("passage_content does not match file content!")
        result['content_fingerprint'] = compute_content_fingerprint(test_case.passage_content)
        result['file_fingerprint'] = compute_content_fingerprint(file_content)
        return result
    
    # Check 3: Expected answer matches fresh extraction (for Q1 as a spot check)
    if test_case.question_type_id == 1:
        try:
            extractor = get_extractor(1, format_name)
            fresh_answer = str(extractor(str(file_path)))
            if fresh_answer != str(test_case.expected_answer):
                result['passed'] = False
                result['errors'].append(
                    f"Expected answer mismatch: DB={test_case.expected_answer}, Fresh={fresh_answer}"
                )
        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Extraction error: {e}")
    
    # Add fingerprint for logging
    result['fingerprint'] = compute_content_fingerprint(test_case.passage_content)
    
    return result


def verify_alignment(config: BenchmarkConfig, verbose: bool = False) -> dict:
    """
    Verify all test cases are correctly aligned.
    
    Returns summary dict with results.
    """
    query = TestCaseQuery(config)
    test_cases = query.fetch_test_cases()
    
    if not test_cases:
        return {'error': 'No test cases found', 'passed': False}
    
    format_name = config.filters.formats[0] if config.filters.formats else 'unknown'
    
    results = {
        'total': len(test_cases),
        'passed': 0,
        'failed': 0,
        'failures': [],
        'format': format_name,
        'num_measures': config.filters.num_measures,
        'timestamp': datetime.now().isoformat(),
    }
    
    # Group by passage for cleaner output
    by_passage = {}
    for tc in test_cases:
        if tc.passage_id not in by_passage:
            by_passage[tc.passage_id] = []
        by_passage[tc.passage_id].append(tc)
    
    print(f"\nVerifying {len(test_cases)} test cases across {len(by_passage)} passages...")
    print(f"Format: {format_name}, Measures: {config.filters.num_measures}")
    print("-" * 60)
    
    for passage_id in sorted(by_passage.keys()):
        passage_tests = by_passage[passage_id]
        passage_passed = True
        passage_errors = []
        
        for tc in passage_tests:
            verification = verify_test_case(tc, format_name)
            
            if verification['passed']:
                results['passed'] += 1
            else:
                results['failed'] += 1
                passage_passed = False
                passage_errors.extend(verification['errors'])
                results['failures'].append(verification)
        
        if verbose or not passage_passed:
            status = "✓" if passage_passed else "✗"
            print(f"  {passage_id}: {status}")
            if passage_errors:
                for err in passage_errors:
                    print(f"    ERROR: {err}")
    
    print("-" * 60)
    print(f"Results: {results['passed']}/{results['total']} passed")
    
    if results['failed'] > 0:
        print(f"\n⚠️  {results['failed']} FAILURES DETECTED!")
        print("DO NOT submit batch until these are fixed.")
    else:
        print("\n✓ All test cases verified successfully!")
        print("Safe to submit batch.")
    
    results['all_passed'] = results['failed'] == 0
    return results


def save_prompts(config: BenchmarkConfig, output_path: Path) -> None:
    """Save all prompts to a file for inspection."""
    query = TestCaseQuery(config)
    test_cases = query.fetch_test_cases()
    
    if not test_cases:
        print("No test cases found")
        return
    
    system_prompt = config.prompt.system_prompt
    
    prompts = []
    for tc in test_cases:
        prompt = build_prompt(
            tc,
            system_prompt,
            include_format_hint=config.prompt.include_format_hint,
        )
        
        # Compute content fingerprint
        fingerprint = compute_content_fingerprint(tc.passage_content)
        
        prompts.append({
            'index': len(prompts),
            'question_id': tc.question_id,
            'passage_id': tc.passage_id,
            'question_type_id': tc.question_type_id,
            'expected_answer': tc.expected_answer,
            'content_fingerprint': fingerprint,
            'prompt_length': len(prompt),
            'prompt_preview': prompt[:500] + '...' if len(prompt) > 500 else prompt,
        })
    
    # Save to file
    with open(output_path, 'w') as f:
        json.dump(prompts, f, indent=2)
    
    print(f"Saved {len(prompts)} prompts to {output_path}")
    
    # Also print summary
    print(f"\nPrompt summary:")
    print(f"  Total: {len(prompts)}")
    print(f"  First: {prompts[0]['question_id']} ({prompts[0]['passage_id']})")
    print(f"  Last: {prompts[-1]['question_id']} ({prompts[-1]['passage_id']})")
    
    # Check for any obvious issues
    prev_passage = None
    for p in prompts:
        if p['question_type_id'] == 1:
            if prev_passage and prev_passage == p['passage_id']:
                print(f"  WARNING: Duplicate Q1 for {p['passage_id']}")
            prev_passage = p['passage_id']


def main():
    parser = argparse.ArgumentParser(description="Verify batch alignment before submission")
    parser.add_argument('--format', type=str, help='Format to verify (abc, humdrum, mei, musicxml)')
    parser.add_argument('--num-measures', type=int, help='Number of measures (1 or 8)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all passages, not just failures')
    parser.add_argument('--save-prompts', action='store_true', help='Save prompts to file for inspection')
    parser.add_argument('--output', type=str, help='Output path for prompts file')
    args = parser.parse_args()
    
    # Load config
    config_path = Path(__file__).parent.parent / 'config.yaml'
    config = BenchmarkConfig.from_yaml(config_path)
    
    # Override from args if provided
    if args.format:
        config.filters.formats = [args.format]
    if args.num_measures:
        config.filters.num_measures = [args.num_measures]
    
    if args.save_prompts:
        output_path = Path(args.output) if args.output else Path('prompts_log.json')
        save_prompts(config, output_path)
    else:
        results = verify_alignment(config, verbose=args.verbose)
        
        # Exit with error code if failures detected
        if not results.get('all_passed', False):
            sys.exit(1)


if __name__ == '__main__':
    main()

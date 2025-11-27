#!/usr/bin/env python3
"""
Test answer extractors against verified answers in the database.

Usage:
    python scripts/test_extractors.py --format abc --question 1
    python scripts/test_extractors.py --format abc --question 1 --passages P-001,P-002,P-003
    python scripts/test_extractors.py --format abc  # Test all questions for ABC
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from answer_extraction.registry import get_extractor


def get_verified_answers(db_path: str, format_name: str, question_type_id: int, passages: list = None):
    """
    Get verified answers from the database.
    
    Returns list of (passage_id, expected_answer) tuples.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    answer_col = f"answer_{format_name}"
    verified_col = f"verified_{format_name}"
    
    query = f"""
        SELECT passage_id, {answer_col}
        FROM questions
        WHERE question_type_id = ?
        AND {verified_col} = 1
        AND {answer_col} IS NOT NULL
    """
    
    if passages:
        placeholders = ','.join('?' * len(passages))
        query += f" AND passage_id IN ({placeholders})"
        cursor.execute(query, [question_type_id] + passages)
    else:
        cursor.execute(query, [question_type_id])
    
    results = cursor.fetchall()
    conn.close()
    
    return results


def get_passage_file_path(passage_id: str, format_name: str) -> Path:
    """Get the file path for a passage."""
    base_path = Path(__file__).parent.parent / 'passages' / format_name
    
    # Determine file extension
    extensions = {
        'abc': '.abc',
        'humdrum': '.krn',
        'mei': '.mei',
        'musicxml': '.musicxml'
    }
    ext = extensions.get(format_name, f'.{format_name}')
    
    return base_path / f"{passage_id}{ext}"


def test_extractor(format_name: str, question_type_id: int, passages: list = None, verbose: bool = True):
    """
    Test an extractor against verified answers.
    
    Returns (passed, failed, errors) counts.
    """
    db_path = Path(__file__).parent.parent / 'benchmark.db'
    
    # Get the extractor
    try:
        extractor = get_extractor(question_type_id, format_name)
    except (KeyError, NotImplementedError) as e:
        print(f"Error: Extractor for Q{question_type_id} {format_name} not available: {e}")
        return 0, 0, 1
    
    # Get verified answers
    verified = get_verified_answers(str(db_path), format_name, question_type_id, passages)
    
    if not verified:
        print(f"No verified answers found for Q{question_type_id} {format_name}")
        return 0, 0, 0
    
    passed = 0
    failed = 0
    errors = 0
    
    for passage_id, expected in verified:
        file_path = get_passage_file_path(passage_id, format_name)
        
        if not file_path.exists():
            if verbose:
                print(f"  {passage_id}: FILE NOT FOUND")
            errors += 1
            continue
        
        try:
            actual = extractor(str(file_path))
            
            # Normalize for comparison (strip whitespace, handle numeric equivalence)
            expected_norm = str(expected).strip()
            actual_norm = str(actual).strip()
            
            # Try numeric comparison for numbers
            try:
                if float(expected_norm) == float(actual_norm):
                    if verbose:
                        print(f"  {passage_id}: ✓ (expected={expected_norm}, got={actual_norm})")
                    passed += 1
                else:
                    if verbose:
                        print(f"  {passage_id}: ✗ MISMATCH (expected={expected_norm}, got={actual_norm})")
                    failed += 1
            except ValueError:
                # String comparison
                if expected_norm == actual_norm:
                    if verbose:
                        print(f"  {passage_id}: ✓ (expected={expected_norm}, got={actual_norm})")
                    passed += 1
                else:
                    if verbose:
                        print(f"  {passage_id}: ✗ MISMATCH (expected={expected_norm}, got={actual_norm})")
                    failed += 1
                    
        except Exception as e:
            if verbose:
                print(f"  {passage_id}: ERROR - {e}")
            errors += 1
    
    return passed, failed, errors


def main():
    parser = argparse.ArgumentParser(description='Test answer extractors')
    parser.add_argument('--format', '-f', required=True, 
                        choices=['abc', 'humdrum', 'mei', 'musicxml'],
                        help='Format to test')
    parser.add_argument('--question', '-q', type=int,
                        help='Question type ID (1-9). If not specified, tests all.')
    parser.add_argument('--passages', '-p', 
                        help='Comma-separated list of passage IDs to test')
    parser.add_argument('--quiet', action='store_true',
                        help='Only show summary')
    
    args = parser.parse_args()
    
    passages = args.passages.split(',') if args.passages else None
    verbose = not args.quiet
    
    if args.question:
        questions = [args.question]
    else:
        questions = range(1, 10)
    
    total_passed = 0
    total_failed = 0
    total_errors = 0
    
    for q in questions:
        print(f"\n=== Testing Q{q} ({args.format}) ===")
        passed, failed, errors = test_extractor(args.format, q, passages, verbose)
        total_passed += passed
        total_failed += failed
        total_errors += errors
        
        if passed + failed + errors > 0:
            print(f"  Summary: {passed} passed, {failed} failed, {errors} errors")
    
    print(f"\n{'='*50}")
    print(f"TOTAL: {total_passed} passed, {total_failed} failed, {total_errors} errors")
    
    if total_failed > 0 or total_errors > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()

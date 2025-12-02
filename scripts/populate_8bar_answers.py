#!/usr/bin/env python3
"""
Populate answers for 8-bar passages using the answer extractors.

This script:
1. Runs extractors on all 8-bar passages (P-046 to P-090)
2. Populates answer_abc, answer_humdrum, answer_mei, answer_musicxml columns
3. Reports cross-format agreement/disagreement for spot-checking

Usage:
    python scripts/populate_8bar_answers.py
    python scripts/populate_8bar_answers.py --dry-run
    python scripts/populate_8bar_answers.py --passages P-046,P-047
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from answer_extraction.registry import get_extractor

FORMATS = ['abc', 'humdrum', 'mei', 'musicxml']
QUESTION_TYPES = range(1, 10)  # Q1-Q9

# File extensions per format
EXTENSIONS = {
    'abc': '.abc',
    'humdrum': '.krn',
    'mei': '.mei',
    'musicxml': '.xml'
}


def get_passage_file_path(passage_id: str, format_name: str) -> Path:
    """Get the file path for a passage."""
    base_path = Path(__file__).parent.parent / 'passages' / format_name
    ext = EXTENSIONS[format_name]
    return base_path / f"{passage_id}{ext}"


def get_8bar_passages(db_path: Path) -> list:
    """Get all 8-bar passage IDs."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT passage_id FROM passages WHERE num_measures = 8 ORDER BY passage_id")
    passages = [row[0] for row in cursor.fetchall()]
    conn.close()
    return passages


def extract_answer(passage_id: str, format_name: str, question_type_id: int) -> tuple:
    """
    Extract answer for a passage/format/question combination.
    
    Returns (answer, error) tuple. If successful, error is None.
    """
    file_path = get_passage_file_path(passage_id, format_name)
    
    if not file_path.exists():
        return None, f"File not found: {file_path}"
    
    try:
        extractor = get_extractor(question_type_id, format_name)
        answer = extractor(str(file_path))
        return str(answer), None
    except Exception as e:
        return None, str(e)


def normalize_answer(answer: str) -> str:
    """Normalize an answer for comparison."""
    if answer is None:
        return None
    
    answer = str(answer).strip()
    
    # Try to normalize numeric values
    try:
        num = float(answer)
        # If it's a whole number, return as int string
        if num == int(num):
            return str(int(num))
        return str(num)
    except ValueError:
        return answer


def check_agreement(answers: dict) -> tuple:
    """
    Check if all formats agree on an answer.
    
    Returns (agrees: bool, unique_answers: set, normalized_answer: str or None)
    """
    # Filter out None values and errors
    valid_answers = {fmt: ans for fmt, ans in answers.items() if ans is not None}
    
    if not valid_answers:
        return False, set(), None
    
    # Normalize answers
    normalized = {fmt: normalize_answer(ans) for fmt, ans in valid_answers.items()}
    unique = set(normalized.values())
    
    if len(unique) == 1:
        return True, unique, list(unique)[0]
    else:
        return False, unique, None


def main():
    parser = argparse.ArgumentParser(description='Populate answers for 8-bar passages')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--passages', '-p',
                        help='Comma-separated list of passage IDs (default: all 8-bar)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed progress')
    args = parser.parse_args()
    
    db_path = Path(__file__).parent.parent / 'benchmark.db'
    
    # Get passages to process
    if args.passages:
        passages = [p.strip() for p in args.passages.split(',')]
    else:
        passages = get_8bar_passages(db_path)
    
    print(f"Processing {len(passages)} passages × {len(QUESTION_TYPES)} questions × {len(FORMATS)} formats")
    print(f"Total extractions: {len(passages) * len(QUESTION_TYPES) * len(FORMATS)}")
    print()
    
    if args.dry_run:
        print("=== DRY RUN MODE ===")
        print()
    
    # Track statistics
    stats = {
        'total_questions': 0,
        'all_agree': 0,
        'disagreements': 0,
        'errors': 0
    }
    
    # Track disagreements for reporting
    disagreements = []
    errors_list = []
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for passage_id in passages:
        if args.verbose:
            print(f"Processing {passage_id}...")
        
        for question_type_id in QUESTION_TYPES:
            stats['total_questions'] += 1
            
            # Extract answers for all formats
            answers = {}
            extraction_errors = {}
            
            for fmt in FORMATS:
                answer, error = extract_answer(passage_id, fmt, question_type_id)
                if error:
                    extraction_errors[fmt] = error
                else:
                    answers[fmt] = answer
            
            # Check for extraction errors
            if extraction_errors:
                stats['errors'] += 1
                errors_list.append({
                    'passage_id': passage_id,
                    'question_type_id': question_type_id,
                    'errors': extraction_errors
                })
                continue
            
            # Check agreement
            agrees, unique_answers, _ = check_agreement(answers)
            
            if agrees:
                stats['all_agree'] += 1
            else:
                stats['disagreements'] += 1
                disagreements.append({
                    'passage_id': passage_id,
                    'question_type_id': question_type_id,
                    'answers': answers.copy()
                })
            
            # Update database (unless dry run)
            if not args.dry_run:
                cursor.execute("""
                    UPDATE questions
                    SET answer_abc = ?,
                        answer_humdrum = ?,
                        answer_mei = ?,
                        answer_musicxml = ?
                    WHERE passage_id = ? AND question_type_id = ?
                """, (
                    answers.get('abc'),
                    answers.get('humdrum'),
                    answers.get('mei'),
                    answers.get('musicxml'),
                    passage_id,
                    question_type_id
                ))
    
    if not args.dry_run:
        conn.commit()
    conn.close()
    
    # Print summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total questions processed: {stats['total_questions']}")
    print(f"All formats agree:         {stats['all_agree']} ({100*stats['all_agree']/stats['total_questions']:.1f}%)")
    print(f"Disagreements:             {stats['disagreements']} ({100*stats['disagreements']/stats['total_questions']:.1f}%)")
    print(f"Extraction errors:         {stats['errors']}")
    print()
    
    # Print disagreements
    if disagreements:
        print("=" * 60)
        print(f"DISAGREEMENTS ({len(disagreements)} total)")
        print("=" * 60)
        for d in disagreements:
            print(f"\n{d['passage_id']} Q{d['question_type_id']}:")
            for fmt, ans in d['answers'].items():
                print(f"  {fmt:10s}: {ans}")
    
    # Print errors
    if errors_list:
        print()
        print("=" * 60)
        print(f"ERRORS ({len(errors_list)} total)")
        print("=" * 60)
        for e in errors_list:
            print(f"\n{e['passage_id']} Q{e['question_type_id']}:")
            for fmt, err in e['errors'].items():
                print(f"  {fmt}: {err}")
    
    if not args.dry_run and stats['disagreements'] == 0 and stats['errors'] == 0:
        print()
        print("✓ All answers populated successfully with full cross-format agreement!")


if __name__ == '__main__':
    main()

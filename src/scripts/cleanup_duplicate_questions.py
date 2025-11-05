#!/usr/bin/env python3
"""
Clean up duplicate questions in the database.

Identifies questions with identical text, answer, and passage,
keeps the earliest one, and deletes duplicates along with their test cases.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "benchmark.db"


def cleanup_duplicate_questions():
    """Remove duplicate questions and their test cases."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n" + "="*70)
    print("CLEANING UP DUPLICATE QUESTIONS")
    print("="*70 + "\n")
    
    # Find all duplicate questions (same passage, question text, and answer)
    cursor.execute("""
        SELECT passage_id, question_text, correct_answer,
               GROUP_CONCAT(question_id ORDER BY question_id) as question_ids,
               COUNT(*) as count
        FROM questions
        GROUP BY passage_id, question_text, correct_answer
        HAVING COUNT(*) > 1
    """)
    
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("✓ No duplicate questions found!")
        conn.close()
        return
    
    print(f"Found {len(duplicates)} sets of duplicate questions:\n")
    
    total_deleted_questions = 0
    total_deleted_tests = 0
    
    for passage_id, q_text, answer, question_ids_str, count in duplicates:
        question_ids = [int(qid) for qid in question_ids_str.split(',')]
        keep_id = question_ids[0]  # Keep the first (earliest) one
        delete_ids = question_ids[1:]  # Delete the rest
        
        print(f"Question: '{q_text[:60]}...'")
        print(f"  Answer: {answer}")
        print(f"  Found {count} duplicates: {question_ids}")
        print(f"  Keeping question_id {keep_id}, deleting {delete_ids}")
        
        # Delete test cases for duplicate questions
        for dup_id in delete_ids:
            cursor.execute("""
                DELETE FROM test_cases 
                WHERE question_id = ?
            """, (dup_id,))
            deleted_tests = cursor.rowcount
            total_deleted_tests += deleted_tests
            if deleted_tests > 0:
                print(f"    Deleted {deleted_tests} test case(s) for question {dup_id}")
        
        # Delete the duplicate questions
        for dup_id in delete_ids:
            cursor.execute("DELETE FROM questions WHERE question_id = ?", (dup_id,))
            total_deleted_questions += 1
        
        print()
    
    conn.commit()
    
    # Show summary
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Deleted {total_deleted_questions} duplicate question(s)")
    print(f"Deleted {total_deleted_tests} associated test case(s)")
    print("="*70 + "\n")
    
    # Show final stats
    cursor.execute("SELECT COUNT(*) FROM passages")
    passage_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM questions")
    question_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM test_cases")
    test_count = cursor.fetchone()[0]
    
    print(f"Final counts:")
    print(f"  Passages:   {passage_count}")
    print(f"  Questions:  {question_count}")
    print(f"  Test cases: {test_count}")
    print()
    
    conn.close()


if __name__ == "__main__":
    cleanup_duplicate_questions()

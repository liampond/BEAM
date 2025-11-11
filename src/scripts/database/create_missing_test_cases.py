#!/usr/bin/env python3
"""
Create test cases for all questions that have answers but no test cases yet.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db_utils import get_connection, create_test_cases


def main():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Find all questions with answers but no test cases
    cursor.execute("""
        SELECT q.question_id, q.question_text
        FROM questions q
        WHERE q.correct_answer IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM test_cases tc WHERE tc.question_id = q.question_id
        )
        ORDER BY q.question_id
    """)
    
    questions = cursor.fetchall()
    conn.close()
    
    if not questions:
        print("No questions found that need test cases.")
        return
    
    print(f"Found {len(questions)} questions that need test cases.")
    print("Creating test cases for each question...\n")
    
    total_created = 0
    for question_id, question_text in questions:
        try:
            count = create_test_cases(question_id)
            total_created += count
        except Exception as e:
            print(f"✗ Error creating test cases for question {question_id}: {e}")
    
    print(f"\nDone! Created {total_created} test cases total.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate questions for the new 8-bar passages.

Copies the same 9 question types used for 1-bar passages.
"""

import sqlite3
from pathlib import Path


def main():
    db_path = Path(__file__).parent.parent / 'benchmark.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get the new 8-bar passages
    cursor.execute("""
        SELECT passage_id 
        FROM passages 
        WHERE num_measures = 8 
        ORDER BY passage_id
    """)
    new_passages = [row[0] for row in cursor.fetchall()]
    
    print(f"Found {len(new_passages)} new 8-bar passages")
    print(f"Range: {new_passages[0]} to {new_passages[-1]}")
    print()
    
    # Get the next available question ID
    cursor.execute("SELECT MAX(CAST(SUBSTR(question_id, 3) AS INTEGER)) FROM questions")
    max_id = cursor.fetchone()[0]
    next_id = max_id + 1 if max_id else 1
    
    print(f"Next question ID: Q-{next_id:03d}")
    print()
    
    # Get all question types
    cursor.execute("SELECT question_type_id FROM question_types ORDER BY question_type_id")
    question_types = [row[0] for row in cursor.fetchall()]
    
    print(f"Will create {len(question_types)} questions per passage")
    print()
    
    # Calculate total questions to create
    total_questions = len(new_passages) * len(question_types)
    
    print(f"Total questions to create: {total_questions}")
    print()
    
    # Confirm
    response = input(f"Create {total_questions} questions for passages {new_passages[0]}-{new_passages[-1]}? [y/N]: ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Create questions
    questions_created = 0
    for passage_id in new_passages:
        for question_type_id in question_types:
            question_id = f"Q-{next_id:03d}"
            
            cursor.execute("""
                INSERT INTO questions (
                    question_id,
                    passage_id,
                    question_type_id,
                    question_text,
                    answer_abc,
                    answer_humdrum,
                    answer_mei,
                    answer_musicxml,
                    verified_abc,
                    verified_humdrum,
                    verified_mei,
                    verified_musicxml
                )
                SELECT 
                    ?,
                    ?,
                    question_type_id,
                    question_template,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    0,
                    0,
                    0,
                    0
                FROM question_types
                WHERE question_type_id = ?
            """, (question_id, passage_id, question_type_id))
            
            next_id += 1
            questions_created += 1
            
            if questions_created % 45 == 0:
                print(f"  Created {questions_created}/{total_questions} questions...")
    
    conn.commit()
    conn.close()
    
    print()
    print(f"✅ Successfully created {questions_created} questions!")
    print(f"   Question IDs: Q-{max_id + 1:03d} to Q-{next_id - 1:03d}")
    print()
    print("Next steps:")
    print("  1. Answer questions for each format")
    print("  2. Update the database with answers")
    print("  3. Verify answers")


if __name__ == '__main__':
    main()

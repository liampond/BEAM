#!/usr/bin/env python3
"""
Fix the questions table in the database:
1. Renumber question IDs to 3 digits (001-009, 010-018, etc.)
2. Ensure all P-001 through P-046 have exactly 9 questions
3. Add missing questions where needed
"""

import sqlite3
from pathlib import Path

# Standard 9 questions for each passage
STANDARD_QUESTIONS = [
    "How many notes are in the lower staff in this passage? Include grace notes and ornaments. Count tied notes only once. Respond with a single number.",
    "How many notes are in the upper staff in this passage? Include grace notes and ornaments. Count tied notes only once. Respond with a single number.",
    "What is the pitch of the first note in the upper staff? If there are multiple simultaneous notes, respond with the highest pitch. Denote octave with scientific pitch notation (e.g., C4).",
    "What is the pitch of the lowest note in the lower staff? Include the octave. Denote octave with scientific pitch notation (e.g., C4).",
    "What is the duration of the longest note in this passage? Respond in the number of quarter notes (e.g., 2 for a half note).",
    "How many different pitch classes are used in the lower staff? Consider pitch classes without regard to octave (i.e., all Cs are the same pitch class). Respond with a number (e.g., 5).",
    "What is the interval between the first and last notes in the upper staff? Respond with the number of semitones as a positive integer (e.g., 5 for a perfect fourth). Use the absolute value.",
    "How many rests are in this passage? Respond with a number (e.g., 3).",
    "What is the duration of the first note in the lower staff? If there are multiple simultaneous notes, respond with the duration of the highest note. Respond in the number of quarter notes (e.g., 2 for a half note)."
]

def main():
    db_path = Path('benchmark.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all passages P-001 through P-046 (the 1-measure passages we want to fix)
    cursor.execute("""
        SELECT p.passage_id, pc.sonata_number, pc.movement
        FROM passages p
        JOIN pieces pc ON p.piece_id = pc.piece_id
        WHERE p.num_measures = 1
        AND p.passage_id <= 'P-046'
        ORDER BY pc.sonata_number, pc.movement
    """)
    passages = cursor.fetchall()
    
    print(f"Found {len(passages)} passages to fix (P-001 through P-046)")
    
    # Backup existing questions
    cursor.execute("DROP TABLE IF EXISTS questions_backup")
    cursor.execute("CREATE TABLE questions_backup AS SELECT * FROM questions")
    print("✓ Backed up existing questions to questions_backup")
    
    # Get the current schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='questions'")
    schema = cursor.fetchone()[0]
    print(f"✓ Retrieved table schema")
    
    # Drop and recreate questions table
    cursor.execute("DROP TABLE questions")
    cursor.execute(schema)
    print("✓ Recreated questions table")
    
    # Insert new questions for P-001 through P-046 with 3-digit IDs
    question_id = 1
    inserted = 0
    
    for passage_id, sonata, movement in passages:
        for i, question_text in enumerate(STANDARD_QUESTIONS, 1):
            qid_str = f"Q-{question_id:03d}"
            
            cursor.execute("""
                INSERT INTO questions (question_id, passage_id, question_text)
                VALUES (?, ?, ?)
            """, (qid_str, passage_id, question_text))
            
            inserted += 1
            question_id += 1
    
    # Copy back P-047+ questions from backup with new IDs starting from 415
    print("Copying back P-047+ questions...")
    cursor.execute("""
        INSERT INTO questions (question_id, passage_id, question_text)
        SELECT 
            'Q-' || SUBSTR('000' || CAST(414 + ROW_NUMBER() OVER (ORDER BY CAST(SUBSTR(passage_id, 3) AS INTEGER), CAST(question_id AS INTEGER)) AS TEXT), -3),
            passage_id,
            question_text
        FROM questions_backup
        WHERE passage_id > 'P-046' OR passage_id NOT LIKE 'P-%'
    """)
    kept = cursor.rowcount
    
    print(f"✓ Inserted {inserted} new questions for P-001 through P-046")
    print(f"✓ Kept {kept} existing questions for passages beyond P-046")
    print(f"✓ Question IDs for P-001 through P-046 now range from Q-001 to Q-{question_id-1:03d}")
    
    # Verify the results
    cursor.execute("""
        SELECT p.passage_id, COUNT(q.question_id) as num_q
        FROM passages p
        LEFT JOIN questions q ON p.passage_id = q.passage_id
        WHERE p.num_measures = 1 AND p.passage_id <= 'P-046'
        GROUP BY p.passage_id
        HAVING num_q != 9
    """)
    issues = cursor.fetchall()
    
    if issues:
        print(f"\n⚠ Warning: {len(issues)} passages still don't have 9 questions:")
        for passage_id, count in issues:
            print(f"  {passage_id}: {count} questions")
    else:
        print("\n✓ All P-001 through P-046 now have exactly 9 questions")
    
    # Show sample
    cursor.execute("""
        SELECT passage_id, question_id, SUBSTR(question_text, 1, 60)
        FROM questions
        WHERE passage_id IN ('P-001', 'P-002', 'P-046')
        ORDER BY passage_id, question_id
    """)
    print("\nSample questions:")
    for row in cursor.fetchall():
        print(f"  {row[0]} {row[1]}: {row[2]}...")
    
    conn.commit()
    conn.close()
    print("\n✓ Database updated successfully")

if __name__ == '__main__':
    main()

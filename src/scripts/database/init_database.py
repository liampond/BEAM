#!/usr/bin/env python3
"""
Initialize the LLM Music Encoding Benchmark database.

Creates SQLite database schema for the new simplified structure:
- question_types: The 9 standard question templates
- passages: Single-measure passages from Mozart piano sonatas
- questions: Benchmark questions with verified answers
- llm_responses: LLM test results
"""

import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent.parent.parent / "benchmark.db"

# Mozart Piano Sonatas metadata (common subset only)
# Format: sonata_num -> (kv_number, movements)
SONATAS = {
    1: ("279", 3),
    2: ("280", 3),
    3: ("281", 3),
    4: ("282", 3),
    5: ("283", 3),
    6: ("284", 2),  # Only movements 1-2 (excluding variation movement 3)
    7: ("309", 3),
    8: ("310", 3),
    9: ("311", 3),
    10: ("330", 3),
    11: ("331", 2),  # Only movements 2-3 (excluding variation movement 1)
    12: ("332", 3),
    13: ("333", 3),
    14: ("457", 3),
    16: ("545", 3),
    18: ("576", 3),
}

# The 9 standard question types
QUESTION_TYPES = [
    'How many notes are in the lower staff in this passage? Include grace notes and ornaments. Count tied notes only once. Respond with a single number.',
    'How many notes are in the upper staff in this passage? Include grace notes and ornaments. Count tied notes only once. Respond with a single number.',
    'What is the pitch of the first note in the upper staff? If there are multiple simultaneous notes, respond with the highest pitch. Denote octave with scientific pitch notation (e.g., C4).',
    'What is the pitch of the lowest note in the lower staff? Include the octave. Denote octave with scientific pitch notation (e.g., C4).',
    'What is the duration of the longest note in this passage? Respond in the number of quarter notes (e.g., 2 for a half note).',
    'How many different pitch classes are used in the lower staff? Consider pitch classes without regard to octave (i.e., all Cs are the same pitch class). Treat enharmonic spellings as distinct pitch classes (e.g., F# and Gb count separately). Respond with a number (e.g., 5).',
    'What is the interval between the first and last notes in the upper staff? Respond with the number of semitones as a positive integer (e.g., 5 for a perfect fourth). Use the absolute value.',
    'How many rests are in this passage? Respond with a number (e.g., 3).',
    'What is the duration of the first note in the lower staff? If there are multiple simultaneous notes, respond with the duration of the highest note. Respond in the number of quarter notes (e.g., 2 for a half note).',
]


def create_schema(conn):
    """Create database schema."""
    cursor = conn.cursor()
    
    # Question types table - the 9 standard question templates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS question_types (
            question_type_id INTEGER PRIMARY KEY,
            question_template TEXT NOT NULL
        )
    """)
    
    # Passages table - single-measure passages from Mozart sonatas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS passages (
            passage_id TEXT PRIMARY KEY,
            num_measures INTEGER NOT NULL,
            sonata_number INTEGER NOT NULL,
            kv_number INTEGER NOT NULL,
            movement INTEGER NOT NULL,
            start_measure_abc INTEGER,
            end_measure_abc INTEGER,
            start_measure_humdrum INTEGER,
            end_measure_humdrum INTEGER,
            start_measure_mei INTEGER,
            end_measure_mei INTEGER,
            start_measure_musicxml INTEGER,
            end_measure_musicxml INTEGER,
            verified_abc BOOLEAN DEFAULT 0,
            verified_humdrum BOOLEAN DEFAULT 0,
            verified_mei BOOLEAN DEFAULT 0,
            verified_musicxml BOOLEAN DEFAULT 0
        )
    """)
    
    # Questions table - benchmark questions with verified answers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            question_id TEXT PRIMARY KEY,
            passage_id TEXT NOT NULL,
            question_text TEXT NOT NULL,
            question_type_id INTEGER,
            answer_abc TEXT,
            answer_humdrum TEXT,
            answer_mei TEXT,
            answer_musicxml TEXT,
            verified_abc BOOLEAN DEFAULT 0,
            verified_humdrum BOOLEAN DEFAULT 0,
            verified_mei BOOLEAN DEFAULT 0,
            verified_musicxml BOOLEAN DEFAULT 0,
            FOREIGN KEY (passage_id) REFERENCES passages(passage_id),
            FOREIGN KEY (question_type_id) REFERENCES question_types(question_type_id)
        )
    """)
    
    # LLM responses table - actual test results
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id TEXT NOT NULL,
            format TEXT NOT NULL,
            llm_model TEXT NOT NULL,
            llm_response TEXT,
            is_correct BOOLEAN,
            response_time REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions(question_id)
        )
    """)
    
    conn.commit()
    print("✓ Database schema created")


def populate_question_types(conn):
    """Populate the question_types table with the 9 standard question templates."""
    cursor = conn.cursor()
    
    for i, template in enumerate(QUESTION_TYPES, 1):
        cursor.execute("""
            INSERT OR IGNORE INTO question_types (question_type_id, question_template)
            VALUES (?, ?)
        """, (i, template))
    
    conn.commit()
    print(f"✓ Populated question_types table with {len(QUESTION_TYPES)} question types")


def print_summary(conn):
    """Print database summary."""
    cursor = conn.cursor()
    
    # Count rows in each table
    cursor.execute("SELECT COUNT(*) FROM question_types")
    question_types_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM passages")
    passages_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions")
    questions_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM llm_responses")
    responses_count = cursor.fetchone()[0]
    
    # Get verified count
    cursor.execute("SELECT COUNT(DISTINCT passage_id) FROM passages WHERE verified_abc = 1")
    verified_passages = cursor.fetchone()[0]
    
    print("\n" + "="*50)
    print("DATABASE SUMMARY")
    print("="*50)
    print(f"Question Types: {question_types_count}")
    print(f"Passages: {passages_count} ({verified_passages} verified)")
    print(f"Questions: {questions_count}")
    print(f"LLM Responses: {responses_count}")
    print("="*50)


def main():
    """Initialize the database."""
    print(f"Creating database at: {DB_PATH}")
    
    # Remove existing database if it exists
    if DB_PATH.exists():
        response = input(f"Database already exists at {DB_PATH}. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
        DB_PATH.unlink()
    
    # Create and populate database
    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        populate_question_types(conn)
        print_summary(conn)
        print(f"\n✓ Database initialized successfully at: {DB_PATH}")
        print("\nNote: This creates an empty database structure.")
        print("Passages and questions can be added using add_question.py")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

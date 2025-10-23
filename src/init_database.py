#!/usr/bin/env python3
"""
Initialize the LLM Music Encoding Benchmark database.

Creates SQLite database schema and populates with metadata for Mozart piano sonatas.
Focuses on the common subset (Sonatas 1-14, 16, 18) excluding variation movements.
"""

import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / "benchmark.db"

# Mozart Piano Sonatas metadata (common subset only)
# Format: sonata_num -> (kv_number, movements, excluded_movements)
SONATAS = {
    1: ("279", 3, []),
    2: ("280", 3, []),
    3: ("281", 3, []),
    4: ("282", 3, []),
    5: ("283", 3, []),
    6: ("284", 3, [3]),  # Exclude movement 3 (variations)
    7: ("309", 3, []),
    8: ("310", 3, []),
    9: ("311", 3, []),
    10: ("330", 3, []),
    11: ("331", 3, [1]),  # Exclude movement 1 (variations)
    12: ("332", 3, []),
    13: ("333", 3, []),
    14: ("457", 3, []),
    16: ("545", 3, []),
    18: ("576", 3, []),
}

# Encoding formats available
FORMATS = ["abc", "mei", "musicxml", "humdrum"]


def create_schema(conn):
    """Create database schema."""
    cursor = conn.cursor()
    
    # Pieces table - individual movements
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pieces (
            piece_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sonata_number INTEGER NOT NULL,
            kv_number TEXT NOT NULL,
            movement INTEGER NOT NULL,
            excluded BOOLEAN DEFAULT 0,
            exclusion_reason TEXT,
            UNIQUE(sonata_number, movement)
        )
    """)
    
    # Encodings table - file references for each format
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS encodings (
            encoding_id INTEGER PRIMARY KEY AUTOINCREMENT,
            piece_id INTEGER NOT NULL,
            format TEXT NOT NULL,
            file_path TEXT NOT NULL,
            available BOOLEAN DEFAULT 1,
            FOREIGN KEY (piece_id) REFERENCES pieces(piece_id),
            UNIQUE(piece_id, format)
        )
    """)
    
    # Passages table - specific excerpts for testing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS passages (
            passage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            piece_id INTEGER NOT NULL,
            granularity TEXT NOT NULL CHECK(granularity IN ('bar', 'phrase', 'section', 'movement')),
            start_measure INTEGER,
            end_measure INTEGER,
            description TEXT,
            FOREIGN KEY (piece_id) REFERENCES pieces(piece_id)
        )
    """)
    
    # Questions table - benchmark questions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            passage_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            difficulty TEXT CHECK(difficulty IN ('easy', 'medium', 'hard')),
            question_type TEXT,
            FOREIGN KEY (passage_id) REFERENCES passages(passage_id)
        )
    """)
    
    # Test cases table - which encodings to test for each question
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_cases (
            test_case_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            encoding_id INTEGER NOT NULL,
            FOREIGN KEY (question_id) REFERENCES questions(question_id),
            FOREIGN KEY (encoding_id) REFERENCES encodings(encoding_id),
            UNIQUE(question_id, encoding_id)
        )
    """)
    
    # LLM responses table - actual test results
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_case_id INTEGER NOT NULL,
            llm_model TEXT NOT NULL,
            llm_response TEXT,
            is_correct BOOLEAN,
            response_time REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (test_case_id) REFERENCES test_cases(test_case_id)
        )
    """)
    
    conn.commit()
    print("✓ Database schema created")


def populate_pieces(conn):
    """Populate pieces and encodings tables with metadata."""
    cursor = conn.cursor()
    
    for sonata_num, (kv, total_movements, excluded_mvmts) in SONATAS.items():
        for movement in range(1, total_movements + 1):
            # Check if this movement should be excluded
            is_excluded = movement in excluded_mvmts
            exclusion_reason = "Variation movement not yet standardized" if is_excluded else None
            
            # Insert piece
            cursor.execute("""
                INSERT INTO pieces (sonata_number, kv_number, movement, excluded, exclusion_reason)
                VALUES (?, ?, ?, ?, ?)
            """, (sonata_num, kv, movement, is_excluded, exclusion_reason))
            
            piece_id = cursor.lastrowid
            
            # Add encoding entries for each format
            for fmt in FORMATS:
                file_path = f"data/{fmt}/{sonata_num:02d}-{movement}.{fmt if fmt != 'musicxml' else 'xml'}"
                if fmt == "humdrum":
                    file_path = f"data/{fmt}/{sonata_num:02d}-{movement}.krn"
                
                cursor.execute("""
                    INSERT INTO encodings (piece_id, format, file_path, available)
                    VALUES (?, ?, ?, 1)
                """, (piece_id, fmt, file_path))
    
    conn.commit()
    
    # Print summary
    total_pieces = cursor.execute("SELECT COUNT(*) FROM pieces").fetchone()[0]
    excluded_pieces = cursor.execute("SELECT COUNT(*) FROM pieces WHERE excluded = 1").fetchone()[0]
    active_pieces = total_pieces - excluded_pieces
    
    print(f"✓ Populated {total_pieces} pieces ({active_pieces} active, {excluded_pieces} excluded)")
    print(f"✓ Created {len(FORMATS)} encoding entries per piece")


def add_example_passage(conn):
    """Add example passage for Sonata 16, Movement 1."""
    cursor = conn.cursor()
    
    # Get piece_id for Sonata 16, Movement 1
    cursor.execute("""
        SELECT piece_id FROM pieces 
        WHERE sonata_number = 16 AND movement = 1
    """)
    piece_id = cursor.fetchone()[0]
    
    # Add a sample bar-level passage (measures 1-4, the opening theme)
    cursor.execute("""
        INSERT INTO passages (piece_id, granularity, start_measure, end_measure, description)
        VALUES (?, 'bar', 1, 4, 'Opening theme - first four measures')
    """, (piece_id,))
    
    conn.commit()
    print(f"✓ Added example passage for Sonata 16, Movement 1 (measures 1-4)")


def print_summary(conn):
    """Print database summary."""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("DATABASE SUMMARY")
    print("="*60)
    
    # Sonatas breakdown
    cursor.execute("""
        SELECT 
            sonata_number,
            kv_number,
            COUNT(*) as movements,
            SUM(CASE WHEN excluded = 1 THEN 1 ELSE 0 END) as excluded
        FROM pieces
        GROUP BY sonata_number
        ORDER BY sonata_number
    """)
    
    print("\nSONATAS IN DATABASE:")
    print(f"{'Sonata':<8} {'K.':>6} {'Mvmts':>7} {'Excluded':>10}")
    print("-" * 35)
    for row in cursor.fetchall():
        sonata, kv, mvmts, excl = row
        print(f"{sonata:<8} {kv:>6} {mvmts:>7} {excl:>10}")
    
    # Overall stats
    cursor.execute("SELECT COUNT(*) FROM pieces WHERE excluded = 0")
    active_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM encodings")
    encoding_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM passages")
    passage_count = cursor.fetchone()[0]
    
    print("\n" + "-" * 60)
    print(f"Total active pieces: {active_count}")
    print(f"Total encoding entries: {encoding_count}")
    print(f"Total passages defined: {passage_count}")
    print(f"Questions defined: 0 (awaiting manual creation)")
    print("="*60)


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
        populate_pieces(conn)
        add_example_passage(conn)
        print_summary(conn)
        print(f"\n✓ Database initialized successfully at: {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

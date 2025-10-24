#!/usr/bin/env python3
"""
Helper utilities for working with the benchmark database.

Provides convenience functions for adding questions, passages, and querying the database.
"""

import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional

DB_PATH = Path(__file__).parent.parent / "benchmark.db"


def get_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def get_piece_id(sonata_number: int, movement: int) -> Optional[int]:
    """Get piece_id for a given sonata and movement."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT piece_id FROM pieces 
        WHERE sonata_number = ? AND movement = ?
    """, (sonata_number, movement))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def get_or_create_passage(sonata_number: int, movement: int, start_measure: int, 
                         end_measure: int, description: str, granularity: str = "bar") -> int:
    """Get existing passage or create new one if it doesn't exist."""
    piece_id = get_piece_id(sonata_number, movement)
    if not piece_id:
        raise ValueError(f"No piece found for Sonata {sonata_number}, Movement {movement}")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if passage already exists
    cursor.execute("""
        SELECT passage_id FROM passages 
        WHERE piece_id = ? AND start_measure = ? AND end_measure = ?
    """, (piece_id, start_measure, end_measure))
    result = cursor.fetchone()
    
    if result:
        passage_id = result[0]
        conn.close()
        print(f"✓ Using existing passage_id {passage_id}: Sonata {sonata_number}, Mvmt {movement}, mm. {start_measure}-{end_measure}")
        return passage_id
    
    # Create new passage
    cursor.execute("""
        INSERT INTO passages (piece_id, granularity, start_measure, end_measure, description)
        VALUES (?, ?, ?, ?, ?)
    """, (piece_id, granularity, start_measure, end_measure, description))
    passage_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    print(f"✓ Added passage_id {passage_id}: Sonata {sonata_number}, Mvmt {movement}, mm. {start_measure}-{end_measure}")
    return passage_id


def add_passage(sonata_number: int, movement: int, start_measure: int, 
                end_measure: int, description: str, granularity: str = "bar") -> int:
    """Add a passage to the database (deprecated - use get_or_create_passage)."""
    return get_or_create_passage(sonata_number, movement, start_measure, end_measure, description, granularity)


def add_question(passage_id: int, question_text: str, correct_answer: str,
                difficulty: str = "medium", question_type: str = "general") -> int:
    """Add a question to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO questions (passage_id, question_text, correct_answer, difficulty, question_type)
        VALUES (?, ?, ?, ?, ?)
    """, (passage_id, question_text, correct_answer, difficulty, question_type))
    question_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    print(f"✓ Added question_id {question_id}: {question_text[:60]}...")
    return question_id


def create_test_cases(question_id: int, formats: List[str] = None) -> int:
    """Create test cases for a question across specified formats."""
    if formats is None:
        formats = ["abc", "mei", "musicxml", "humdrum"]
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get passage and piece info
    cursor.execute("""
        SELECT p.piece_id FROM questions q
        JOIN passages p ON q.passage_id = p.passage_id
        WHERE q.question_id = ?
    """, (question_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise ValueError(f"No question found with id {question_id}")
    
    piece_id = result[0]
    
    # Create test cases for each format
    count = 0
    for fmt in formats:
        cursor.execute("""
            INSERT INTO test_cases (question_id, encoding_id)
            SELECT ?, encoding_id FROM encodings
            WHERE piece_id = ? AND format = ?
        """, (question_id, piece_id, fmt))
        count += cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"✓ Created {count} test cases for question_id {question_id}")
    return count


def list_passages(sonata_number: int = None, movement: int = None):
    """List all passages, optionally filtered by sonata/movement."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            p.passage_id,
            pc.sonata_number,
            pc.kv_number,
            pc.movement,
            p.start_measure,
            p.end_measure,
            p.granularity,
            p.description
        FROM passages p
        JOIN pieces pc ON p.piece_id = pc.piece_id
    """
    params = []
    
    if sonata_number:
        query += " WHERE pc.sonata_number = ?"
        params.append(sonata_number)
        if movement:
            query += " AND pc.movement = ?"
            params.append(movement)
    
    query += " ORDER BY pc.sonata_number, pc.movement, p.start_measure"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        print("No passages found.")
        return
    
    print("\nPASSAGES:")
    print(f"{'ID':<5} {'Sonata':<8} {'K.':<6} {'Mvmt':<5} {'Measures':<12} {'Gran.':<8} {'Description':<40}")
    print("-" * 100)
    for row in results:
        pid, sonata, kv, mvmt, start, end, gran, desc = row
        measures = f"{start}-{end}" if start != end else str(start)
        desc = (desc[:37] + "...") if len(desc) > 40 else desc
        print(f"{pid:<5} {sonata:<8} {kv:<6} {mvmt:<5} {measures:<12} {gran:<8} {desc:<40}")


def list_questions(passage_id: int = None):
    """List all questions, optionally filtered by passage_id."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            q.question_id,
            q.passage_id,
            q.question_text,
            q.correct_answer,
            q.difficulty,
            q.question_type,
            (SELECT COUNT(*) FROM test_cases WHERE question_id = q.question_id) as test_count
        FROM questions q
    """
    
    if passage_id:
        query += " WHERE q.passage_id = ?"
        params = [passage_id]
    else:
        params = []
    
    query += " ORDER BY q.passage_id, q.question_id"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        print("No questions found.")
        return
    
    print("\nQUESTIONS:")
    print(f"{'ID':<5} {'Pass':<5} {'Question':<50} {'Answer':<20} {'Diff':<8} {'Type':<15} {'Tests':<6}")
    print("-" * 120)
    for row in results:
        qid, pid, text, answer, diff, qtype, tcount = row
        text = (text[:47] + "...") if len(text) > 50 else text
        answer = (answer[:17] + "...") if len(answer) > 20 else answer
        print(f"{qid:<5} {pid:<5} {text:<50} {answer:<20} {diff:<8} {qtype:<15} {tcount:<6}")


def show_stats():
    """Show database statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM pieces WHERE excluded = 0")
    active_pieces = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM passages")
    passages = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions")
    questions = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM test_cases")
    test_cases = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM llm_responses")
    responses = cursor.fetchone()[0]
    
    conn.close()
    
    print("\n" + "="*60)
    print("DATABASE STATISTICS")
    print("="*60)
    print(f"Active pieces:     {active_pieces}")
    print(f"Passages defined:  {passages}")
    print(f"Questions:         {questions}")
    print(f"Test cases:        {test_cases}")
    print(f"LLM responses:     {responses}")
    print("="*60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python db_utils.py stats")
        print("  python db_utils.py passages [sonata_number] [movement]")
        print("  python db_utils.py questions [passage_id]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "stats":
        show_stats()
    elif command == "passages":
        sonata = int(sys.argv[2]) if len(sys.argv) > 2 else None
        movement = int(sys.argv[3]) if len(sys.argv) > 3 else None
        list_passages(sonata, movement)
    elif command == "questions":
        passage_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
        list_questions(passage_id)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

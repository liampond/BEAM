#!/usr/bin/env python3
"""
Helper utilities for working with the benchmark database.

Provides convenience functions for adding questions, passages, and querying the database.
"""

import sqlite3
import random
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
    """Add a question to the database (for backward compatibility)."""
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


def add_multiple_choice_question(passage_id: int, question_text: str, 
                                 choices: List[Tuple[str, bool]],
                                 difficulty: str = "medium", 
                                 question_type: str = "general") -> int:
    """
    Add a multiple choice question to the database with A/B/C/D format.
    
    Args:
        passage_id: ID of the passage this question is about
        question_text: The question text
        choices: List of (choice_text, is_correct) tuples (must have exactly 4 choices with 1 correct)
        difficulty: Question difficulty (easy, medium, hard)
        question_type: Type of question (general, harmonic, melodic, rhythmic, formal)
    
    Returns:
        question_id of the newly created question
    """
    # Validate that there are exactly 4 choices
    if len(choices) != 4:
        raise ValueError(f"Multiple choice question must have exactly 4 choices, got {len(choices)}")
    
    # Validate that there's exactly one correct answer
    correct_count = sum(1 for _, is_correct in choices if is_correct)
    if correct_count != 1:
        raise ValueError(f"Multiple choice question must have exactly 1 correct answer, got {correct_count}")
    
    # Get the correct answer text
    correct_answer = next(text for text, is_correct in choices if is_correct)
    
    # Extract just the text from choices
    all_options = [text for text, is_correct in choices]
    
    # Randomly shuffle the options
    shuffled_options = all_options.copy()
    random.shuffle(shuffled_options)
    
    # Find which position has the correct answer
    correct_index = shuffled_options.index(correct_answer)
    correct_letter = ['A', 'B', 'C', 'D'][correct_index]
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Insert question with A/B/C/D options
    cursor.execute("""
        INSERT INTO questions (passage_id, question_text, correct_answer, 
                              option_a, option_b, option_c, option_d, correct_option,
                              difficulty, question_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (passage_id, question_text, correct_answer,
          shuffled_options[0], shuffled_options[1], shuffled_options[2], shuffled_options[3],
          correct_letter, difficulty, question_type))
    question_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    print(f"✓ Added multiple choice question_id {question_id} (Correct answer: {correct_letter})")
    return question_id


def get_question_choices(question_id: int) -> List[Tuple[str, bool]]:
    """Get all answer choices for a question in A/B/C/D format."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT option_a, option_b, option_c, option_d, correct_option
        FROM questions 
        WHERE question_id = ?
    """, (question_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or not result[0]:
        return []
    
    opt_a, opt_b, opt_c, opt_d, correct = result
    return [
        (opt_a, correct == 'A'),
        (opt_b, correct == 'B'),
        (opt_c, correct == 'C'),
        (opt_d, correct == 'D'),
    ]


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
    print(f"{'ID':<8} {'Sonata':<8} {'K.':<6} {'Mvmt':<5} {'Measures':<12} {'Gran.':<8} {'Description':<40}")
    print("-" * 100)
    for row in results:
        pid, sonata, kv, mvmt, start, end, gran, desc = row
        pid_str = f"P-{pid:03d}"
        measures = f"{start}-{end}" if start != end else str(start)
        desc = (desc[:37] + "...") if len(desc) > 40 else desc
        print(f"{pid_str:<8} {sonata:<8} {kv:<6} {mvmt:<5} {measures:<12} {gran:<8} {desc:<40}")


def list_questions(passage_id: int = None, verbose: bool = False):
    """List all questions, optionally filtered by passage_id."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            q.question_id,
            q.passage_id,
            q.question_text,
            q.option_a,
            q.option_b,
            q.option_c,
            q.option_d,
            q.correct_option,
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
    
    if not results:
        print("No questions found.")
        conn.close()
        return
    
    if not verbose:
        # Compact view
        print("\nQUESTIONS:")
        print(f"{'ID':<8} {'Passage':<9} {'Question':<45} {'A':<15} {'B':<15} {'C':<15} {'D':<15} {'Answer':<8} {'Difficulty':<12} {'Type':<12}")
        print("-" * 168)
        for row in results:
            qid, pid, text, opt_a, opt_b, opt_c, opt_d, correct, diff, qtype, tcount = row
            qid_str = f"Q-{qid:03d}"
            pid_str = f"P-{pid:03d}"
            text = (text[:42] + "...") if len(text) > 45 else text
            opt_a = (opt_a[:12] + "...") if opt_a and len(opt_a) > 15 else (opt_a or "")
            opt_b = (opt_b[:12] + "...") if opt_b and len(opt_b) > 15 else (opt_b or "")
            opt_c = (opt_c[:12] + "...") if opt_c and len(opt_c) > 15 else (opt_c or "")
            opt_d = (opt_d[:12] + "...") if opt_d and len(opt_d) > 15 else (opt_d or "")
            correct_str = correct or "-"
            print(f"{qid_str:<8} {pid_str:<9} {text:<45} {opt_a:<15} {opt_b:<15} {opt_c:<15} {opt_d:<15} {correct_str:<8} {diff:<12} {qtype:<12}")
    else:
        # Verbose view
        print("\nQUESTIONS (Verbose):")
        print("="*80)
        for row in results:
            qid, pid, text, opt_a, opt_b, opt_c, opt_d, correct, diff, qtype, tcount = row
            qid_str = f"Q-{qid:03d}"
            pid_str = f"P-{pid:03d}"
            
            print(f"\n{qid_str} | Passage: {pid_str} | {diff} | {qtype}")
            print(f"Question: {text}")
            if opt_a or opt_b or opt_c or opt_d:
                marker_a = "✓" if correct == "A" else " "
                marker_b = "✓" if correct == "B" else " "
                marker_c = "✓" if correct == "C" else " "
                marker_d = "✓" if correct == "D" else " "
                print(f"  {marker_a} A. {opt_a or ''}")
                print(f"  {marker_b} B. {opt_b or ''}")
                print(f"  {marker_c} C. {opt_c or ''}")
                print(f"  {marker_d} D. {opt_d or ''}")
                print(f"  Correct: {correct}")
            print(f"  Test cases: {tcount}")
            print("-"*80)
    
    conn.close()


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
        print("  python db_utils.py questions [passage_id] [-v|--verbose]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "stats":
        show_stats()
    elif command == "passages":
        sonata = int(sys.argv[2]) if len(sys.argv) > 2 else None
        movement = int(sys.argv[3]) if len(sys.argv) > 3 else None
        list_passages(sonata, movement)
    elif command == "questions":
        passage_id = None
        verbose = False
        
        for arg in sys.argv[2:]:
            if arg in ['-v', '--verbose']:
                verbose = True
            else:
                passage_id = int(arg)
        
        list_questions(passage_id, verbose)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

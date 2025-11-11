#!/usr/bin/env python3
"""
Review and update format-specific answers for passages.
Goes through one format at a time for all passages.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db_utils import get_connection
from core.question_utils import get_auto_generated_passages, get_question_range_for_passage


def fetch_questions_for_passage(conn, passage_id: int, format_name: str):
    """Fetch all questions for a passage with format-specific answers."""
    cursor = conn.cursor()
    
    answer_col = f"answer_{format_name}"
    cursor.execute(f"""
        SELECT question_id, question_text, {answer_col}
        FROM questions
        WHERE passage_id = ?
        ORDER BY question_id
    """, (passage_id,))
    
    return cursor.fetchall()


def update_answer(conn, question_id: int, format_name: str, new_answer: str):
    """Update a format-specific answer."""
    cursor = conn.cursor()
    answer_col = f"answer_{format_name}"
    
    cursor.execute(f"""
        UPDATE questions
        SET {answer_col} = ?
        WHERE question_id = ?
    """, (new_answer, question_id))
    
    conn.commit()


def review_format(format_name: str):
    """Review all passages for a specific format."""
    conn = get_connection()
    
    # Get all passages with auto-generated questions
    passage_ids = get_auto_generated_passages(conn)
    
    if not passage_ids:
        print("No passages found with auto-generated questions.")
        conn.close()
        return
    
    # Get passage details
    cursor = conn.cursor()
    passages = []
    for pid in passage_ids:
        cursor.execute("""
            SELECT p.passage_id, pc.sonata_number, pc.movement,
                   p.start_measure, p.end_measure
            FROM passages p
            JOIN pieces pc ON p.piece_id = pc.piece_id
            WHERE p.passage_id = ?
        """, (pid,))
        
        passage_data = cursor.fetchone()
        if passage_data:
            passages.append(passage_data)
    
    print(f"\n{'='*80}")
    print(f"REVIEWING {format_name.upper()} FORMAT")
    print(f"{'='*80}")
    print(f"Total passages: {len(passages)}\n")
    
    for i, (passage_id, sonata, movement, start, end) in enumerate(passages, 1):
        measures = f"{start}-{end}" if start != end else str(start)
        
        print(f"\n{'='*80}")
        print(f"Passage {i}/{len(passages)}: P-{passage_id:03d}")
        print(f"Sonata {sonata}, Movement {movement}, Measures {measures}")
        print(f"{'='*80}\n")
        
        # Fetch questions for this passage
        questions = fetch_questions_for_passage(conn, passage_id, format_name)
        
        if not questions:
            print("No questions found for this passage.")
            continue
        
        # Review each question
        for qid, qtext, current_answer in questions:
            print(f"\n[Q-{qid:03d}] {qtext}")
            print(f"Current {format_name} answer: {current_answer}")
            
            new_answer = input(f"New answer (press Enter to keep current): ").strip()
            
            if new_answer:
                update_answer(conn, qid, format_name, new_answer)
                print(f"✓ Updated to: {new_answer}")
            else:
                print("↺ Kept existing answer.")
        
        # Ask if user wants to continue
        if i < len(passages):
            cont = input(f"\nContinue to next passage? (y/n): ").strip().lower()
            if cont != 'y':
                print("\nStopping review.")
                break
    
    conn.close()
    
    print(f"\n{'='*80}")
    print(f"✅ Finished reviewing {format_name.upper()} format")
    print(f"{'='*80}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Review format-specific answers for passages")
    parser.add_argument("format", choices=["abc", "mei", "musicxml", "humdrum"],
                       help="Format to review")
    parser.add_argument("--start-passage", type=int, help="Start from this passage ID")
    
    args = parser.parse_args()
    
    review_format(args.format)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""List all passages that have auto-generated questions to review."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db_utils import get_connection
from core.question_utils import get_auto_generated_passages, get_question_range_for_passage


def main():
    conn = get_connection()
    
    # Get all passages with auto-generated questions
    passage_ids = get_auto_generated_passages(conn)
    
    if not passage_ids:
        print("No passages found with auto-generated questions.")
        conn.close()
        return
    
    # Get details for each passage
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
            min_q, max_q = get_question_range_for_passage(conn, pid)
            passages.append((*passage_data, max_q - min_q + 1 if min_q and max_q else 0))
    
    conn.close()
    
    print(f"Found {len(passages)} passages with auto-generated questions to review:\n")
    print(f"{'Passage':<10} {'Sonata':<8} {'Mvt':<5} {'Measures':<12} {'Questions':<10} {'Command':<50}")
    print("=" * 100)
    
    for passage_id, sonata, movement, start, end, count in passages:
        measures = f"{start}-{end}" if start != end else str(start)
        command = f"PYTHONPATH=src .venv/bin/python -m cli.review_passage {passage_id}"
        print(f"P-{passage_id:03d}      {sonata:<8} {movement:<5} {measures:<12} {count:<10} {command}")
    
    print("\n" + "=" * 100)
    print(f"\nTotal: {len(passages)} passages to review")
    print(f"\nTo review a passage:")
    print(f"  1. Open the ABC file: data/question_passages_abc/P###.abc")
    print(f"  2. Render it to see the notation")
    print(f"  3. Run: PYTHONPATH=src .venv/bin/python -m cli.review_passage ###")
    print(f"  4. Verify/update each answer")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Interactive CLI to review and update answers for a passage."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

from core.db_utils import DB_PATH as DEFAULT_DB_PATH


def get_connection(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def fetch_passage_summary(conn: sqlite3.Connection, passage_id: int) -> Optional[Tuple[int, int, int, int, int]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pc.sonata_number, pc.movement, p.start_measure, p.end_measure, p.passage_id
        FROM passages p
        JOIN pieces pc ON p.piece_id = pc.piece_id
        WHERE p.passage_id = ?
        """,
        (passage_id,),
    )
    row = cursor.fetchone()
    return row if row else None


def fetch_questions(conn: sqlite3.Connection, passage_id: int) -> List[Tuple[int, str, str]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT question_id, question_text, IFNULL(correct_answer, '')
        FROM questions
        WHERE passage_id = ?
        ORDER BY question_id
        """,
        (passage_id,),
    )
    return cursor.fetchall()


def update_answer(conn: sqlite3.Connection, question_id: int, answer: str) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE questions
        SET correct_answer = ?
        WHERE question_id = ?
        """,
        (answer, question_id),
    )
    conn.commit()


def prompt_for_answers(conn: sqlite3.Connection, passage_id: int) -> None:
    summary = fetch_passage_summary(conn, passage_id)
    if summary is None:
        print(f"No passage found with ID {passage_id}.")
        return

    sonata, movement, start_measure, end_measure, _ = summary
    measure_label = f"{start_measure}" if start_measure == end_measure else f"{start_measure}-{end_measure}"
    header = f"Passage P-{passage_id:03d} | Sonata {sonata:02d}, Movement {movement} | Measures {measure_label}"
    print("=" * len(header))
    print(header)
    print("=" * len(header))

    questions = fetch_questions(conn, passage_id)
    if not questions:
        print("No questions found for this passage.")
        return

    for question_id, question_text, current_answer in questions:
        print(f"\n[Q-{question_id:03d}] {question_text}")
        display_answer = current_answer if current_answer else "(blank)"
        print(f"Current answer: {display_answer}")
        new_answer = input("New answer (press Enter to keep current): ").strip()
        if new_answer:
            update_answer(conn, question_id, new_answer)
            print("✓ Answer updated.")
        else:
            print("↺ Kept existing answer.")

    print("\nAll questions processed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review questions for a passage and update answers interactively.")
    parser.add_argument("passage_id", type=int, help="Passage ID to review (e.g., 24)")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the benchmark database (defaults to repository benchmark.db)",
    )
    args = parser.parse_args()

    conn = get_connection(args.db)
    try:
        prompt_for_answers(conn, args.passage_id)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

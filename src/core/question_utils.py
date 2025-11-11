#!/usr/bin/env python3
"""
Helper utilities for working with questions and passages.
Provides functions to identify auto-generated vs manual questions without hardcoding IDs.
"""

import sqlite3
from typing import Tuple


def get_question_type_boundary(conn: sqlite3.Connection) -> int:
    """
    Get the boundary between auto-generated and manual questions.
    Auto-generated questions have certain types (melodic, rhythmic) that manual don't have much of.
    
    Returns the question_id where manual questions start (auto-generated are < this number).
    """
    cursor = conn.cursor()
    
    # Find the first question that's likely manual by looking for question_type='general'
    # and checking if there's a cluster of 'melodic'/'rhythmic' before it
    cursor.execute("""
        SELECT MIN(question_id)
        FROM questions
        WHERE question_type = 'general'
        AND (
            SELECT COUNT(*)
            FROM questions q2
            WHERE q2.question_id < questions.question_id
            AND q2.question_type IN ('melodic', 'rhythmic')
        ) > 50  -- More than 50 melodic/rhythmic questions before this one
    """)
    
    boundary = cursor.fetchone()[0]
    return boundary if boundary else 999999  # Return a large number if no boundary found


def is_auto_generated_question(conn: sqlite3.Connection, question_id: int) -> bool:
    """Check if a question ID is auto-generated (vs manually created)."""
    boundary = get_question_type_boundary(conn)
    return question_id < boundary


def get_auto_generated_passages(conn: sqlite3.Connection) -> list:
    """
    Get all passages that have auto-generated questions.
    Returns list of passage_ids.
    """
    cursor = conn.cursor()
    boundary = get_question_type_boundary(conn)
    
    cursor.execute("""
        SELECT DISTINCT p.passage_id
        FROM passages p
        JOIN questions q ON p.passage_id = q.passage_id
        WHERE q.question_id < ?
        ORDER BY p.passage_id
    """, (boundary,))
    
    return [row[0] for row in cursor.fetchall()]


def get_question_range_for_passage(conn: sqlite3.Connection, passage_id: int) -> Tuple[int | None, int | None]:
    """
    Get the min and max question IDs for a specific passage.
    Returns (min_qid, max_qid) or (None, None) if no questions found.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MIN(question_id), MAX(question_id)
        FROM questions
        WHERE passage_id = ?
    """, (passage_id,))
    
    result = cursor.fetchone()
    return result if result[0] is not None else (None, None)


def get_passage_question_count(conn: sqlite3.Connection, passage_id: int) -> int:
    """Get the number of questions for a specific passage."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM questions
        WHERE passage_id = ?
    """, (passage_id,))
    
    return cursor.fetchone()[0]

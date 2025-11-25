
"""
Lightweight LLM integration utilities for the benchmark.

Provides a send_prompt() wrapper with multiple backend support (mock by default),
prompt builder, and small DB helpers to fetch test cases and persist responses.

"""

import json
import sqlite3
from typing import Dict, Any, List, Optional
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "benchmark.db"


def build_prompt(question_text: str, passage_text: str) -> str:
    """Construct a clear prompt by combining passage content and question."""
    
    system_prompt = (f"You are a music encoding parser. Your task is to read any input music encoding (e.g., MusicXML, MIDI, ABC, MEI, LilyPond) and extract the information needed to answer the prompt."
    "Output only valid JSON, including only the fields relevant to the question."
    "Possible fields are: \"pitch\" (e.g., \"C4\"), \"duration\" (e.g., \"quarter\" or ticks), \"start_time\" (seconds or ticks), \"velocity\" (0–127), \"measure\" (integer). Do not include explanations or extra text.")

    prompt = (
        f"{system_prompt}\n\n"
        f"Passage:\n{passage_text}\n\n"
        f"Question: {question_text}\n\n"
    )
    return prompt


def get_connection():
    return sqlite3.connect(DB_PATH)


def fetch_test_cases(conn: Optional[sqlite3.Connection] = None, question_id: Optional[int] = None, limit: Optional[int] = None, formats: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Fetch test cases (joined to encodings, questions, passages) from the DB.

    Returns a list of dicts containing keys needed to run the benchmark:
    - test_case_id, question_id, question_type, question_text, correct_answer, encoding_id,
      format, file_path, piece_id, passage_id, start_measure, end_measure, granularity
    """
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    cur = conn.cursor()
    query = """
        SELECT
            tc.test_case_id,
            tc.question_id,
            q.question_type,
            q.question_text,
            CASE e.format
                WHEN 'musicxml' THEN q.answer_musicxml
                WHEN 'abc' THEN q.answer_abc
                WHEN 'mei' THEN q.answer_mei
                WHEN 'humdrum' THEN q.answer_humdrum
                ELSE q.answer_humdrum
            END AS correct_answer,
            e.encoding_id,
            e.format,
            e.file_path,
            e.piece_id,
            p.passage_id,
            p.start_measure,
            p.end_measure,
            p.granularity,
            CASE e.format
                WHEN 'musicxml' THEN q.verified_musicxml
                WHEN 'abc' THEN q.verified_abc
                WHEN 'mei' THEN q.verified_mei
                WHEN 'humdrum' THEN q.verified_humdrum
                ELSE 0
            END AS verified_answer
        FROM test_cases tc
        JOIN questions q ON tc.question_id = q.question_id
        JOIN encodings e ON tc.encoding_id = e.encoding_id
        LEFT JOIN passages p ON q.passage_id = p.passage_id
    """

    params: List[Any] = []
    filters: List[str] = []
    if question_id:
        filters.append("tc.question_id = ?")
        params.append(question_id)
    if formats:
        placeholders = ','.join('?' for _ in formats)
        filters.append(f"e.format IN ({placeholders})")
        params.extend(formats)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += " ORDER BY tc.test_case_id"
    if limit:
        query += f" LIMIT {int(limit)}"

    cur.execute(query, params)
    rows = cur.fetchall()

    keys = [
        "test_case_id",
        "question_id",
        "question_type",
        "question_text",
        "correct_answer",
        "encoding_id",
        "format",
        "file_path",
        "piece_id",
        "passage_id",
        "start_measure",
        "end_measure",
        "granularity",
        "verified_answer",
    ]

    results: List[Dict[str, Any]] = [dict(zip(keys, row)) for row in rows]

    if own_conn:
        conn.close()

    return results


def insert_llm_response(conn: sqlite3.Connection, test_case_id: int, llm_model: str, llm_response: str, is_correct: Optional[bool], metadata: Optional[Dict[str, Any]] = None) -> int:
    """Insert a response row into llm_responses and return inserted id.
    We store a JSON blob containing the raw response and metadata in the
    `llm_response` text field to keep a single column schema.
    """
    cur = conn.cursor()
    payload: Dict[str, Any] = {"response": llm_response}
    if metadata:
        payload["metadata"] = metadata

    payload_json = json.dumps(payload, ensure_ascii=False)

    cur.execute(
        "INSERT INTO llm_responses (test_case_id, llm_model, llm_response, is_correct) VALUES (?, ?, ?, ?)",
        (test_case_id, llm_model, payload_json, is_correct),
    )
    conn.commit()
    last_id = cur.lastrowid
    return int(last_id) if last_id is not None else 0

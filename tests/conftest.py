"""
Shared pytest fixtures and configuration for answer extraction tests.
"""

import pytest
import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Database path
DB_PATH = PROJECT_ROOT / "beam.db"

# Passages directory
PASSAGES_DIR = PROJECT_ROOT / "passages"


@pytest.fixture
def db_connection():
    """Provide a database connection for tests."""
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


def get_verified_answers(
    format_name: str, 
    question_type_id: int, 
    passages: Optional[List[str]] = None
) -> List[Tuple[str, str]]:
    """
    Get verified answers from the database.
    
    Args:
        format_name: The format (abc, humdrum, mei, musicxml)
        question_type_id: The question type ID (1-9)
        passages: Optional list of specific passage IDs to test
    
    Returns:
        List of (passage_id, expected_answer) tuples
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    query = """
        SELECT passage_id, answer
        FROM ground_truth
        WHERE qtype = ?
        AND format = ?
        AND verified = 1
        AND answer IS NOT NULL
    """
    params: list = [question_type_id, format_name]

    if passages:
        placeholders = ','.join('?' * len(passages))
        query += f" AND passage_id IN ({placeholders})"
        params.extend(passages)

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return results


def get_passage_path(passage_id: str, format_name: str) -> Path:
    """
    Get the file path for a passage.
    
    Args:
        passage_id: The passage ID (e.g., "P-001")
        format_name: The format (abc, humdrum, mei, musicxml)
    
    Returns:
        Path to the passage file
    """
    extensions = {
        'abc': '.abc',
        'humdrum': '.krn',
        'mei': '.mei',
        'musicxml': '.xml'
    }
    ext = extensions.get(format_name, f'.{format_name}')
    
    return PASSAGES_DIR / format_name / f"{passage_id}{ext}"


def compare_answers(expected: str, actual: str) -> bool:
    """
    Compare expected and actual answers with appropriate normalization.
    
    Handles:
    - Whitespace differences
    - Numeric equivalence (e.g., "1.0" == "1")
    - Case sensitivity for pitch names
    
    Args:
        expected: The expected answer
        actual: The actual answer from extractor
    
    Returns:
        True if answers match, False otherwise
    """
    expected_norm = str(expected).strip()
    actual_norm = str(actual).strip()
    
    # Try numeric comparison first
    try:
        return float(expected_norm) == float(actual_norm)
    except ValueError:
        pass
    
    # String comparison (case-sensitive for pitches)
    return expected_norm == actual_norm

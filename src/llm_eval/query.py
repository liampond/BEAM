"""
Test Case Query Builder

Generates test cases from the database based on filter configuration.
Handles the mapping between passages, questions, and file paths.

Design:
    - Query database for questions matching filters
    - Resolve file paths for each format
    - Load passage content
    - Return ready-to-use TestCase objects
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterator
import sqlite3

from .config import BenchmarkConfig, FilterConfig


@dataclass
class TestCase:
    """
    A single test case ready for LLM evaluation.
    
    Contains all information needed to:
        1. Send prompt to LLM
        2. Evaluate response
        3. Store results
    """
    # Identifiers
    question_id: str  # e.g., "Q-001"
    passage_id: str  # e.g., "P-001"
    format: str  # e.g., "abc"
    
    # Question data
    question_text: str
    question_type_id: int
    expected_answer: str
    
    # Passage data
    passage_content: str
    passage_file_path: str
    num_measures: int
    
    # Metadata
    verified: bool = False
    
    @property
    def test_id(self) -> str:
        """Unique identifier for this test case."""
        return f"{self.question_id}_{self.format}"
    
    @property
    def custom_id(self) -> str:
        """ID for batch API (must be <= 64 chars)."""
        return f"{self.question_id}_{self.passage_id}_{self.format}"


class TestCaseQuery:
    """
    Query builder for fetching test cases from database.
    
    Uses the actual schema:
        - passages: passage_id, num_measures, verified_{format}
        - questions: question_id, passage_id, question_type_id, answer_{format}, verified_{format}
        - question_types: question_type_id, question_text
    """
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.db_path = config.project_root / "benchmark.db"
        self.passages_dir = config.project_root / "passages"
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)
    
    def _build_query(self, format_name: str) -> tuple[str, list]:
        """
        Build SQL query for a specific format.
        
        Returns:
            (query_string, parameters)
        """
        filters = self.config.filters
        
        # Select answer and verified columns based on format
        answer_col = f"q.answer_{format_name}"
        verified_col = f"q.verified_{format_name}"
        passage_verified_col = f"p.verified_{format_name}"
        
        query = f"""
            SELECT 
                q.question_id,
                q.passage_id,
                q.question_type_id,
                qt.question_template,
                {answer_col} as expected_answer,
                {verified_col} as verified,
                p.num_measures,
                '{format_name}' as format
            FROM questions q
            JOIN passages p ON q.passage_id = p.passage_id
            JOIN question_types qt ON q.question_type_id = qt.question_type_id
            WHERE 1=1
        """
        
        params: List[Any] = []
        
        # Verified filter
        if filters.verified_only:
            query += f" AND {verified_col} = 1"
        
        # Passage filters
        if filters.passages:
            placeholders = ','.join('?' * len(filters.passages))
            query += f" AND q.passage_id IN ({placeholders})"
            params.extend(filters.passages)
        
        # Num measures filter
        if filters.num_measures:
            placeholders = ','.join('?' * len(filters.num_measures))
            query += f" AND p.num_measures IN ({placeholders})"
            params.extend(filters.num_measures)
        
        # Question ID filter
        if filters.question_ids:
            placeholders = ','.join('?' * len(filters.question_ids))
            query += f" AND q.question_id IN ({placeholders})"
            params.extend(filters.question_ids)
        
        # Question type filter
        if filters.question_types:
            placeholders = ','.join('?' * len(filters.question_types))
            query += f" AND q.question_type_id IN ({placeholders})"
            params.extend(filters.question_types)
        
        # Filter out NULL answers
        query += f" AND {answer_col} IS NOT NULL"
        
        # Order for consistency
        query += " ORDER BY q.question_id"
        
        # Limit
        if filters.limit:
            query += f" LIMIT {int(filters.limit)}"
        
        return query, params
    
    def _get_passage_path(self, passage_id: str, format_name: str) -> Path:
        """Get file path for a passage in a specific format."""
        extension_map = {
            "abc": "abc",
            "humdrum": "krn",
            "mei": "mei",
            "musicxml": "xml",  # MusicXML files use .xml extension
        }
        
        ext = extension_map.get(format_name, format_name)
        return self.passages_dir / format_name / f"{passage_id}.{ext}"
    
    def _load_passage_content(self, path: Path) -> str:
        """Load passage content from file."""
        if not path.exists():
            return f"<FILE_NOT_FOUND: {path}>"
        return path.read_text()
    
    def fetch_test_cases(self) -> List[TestCase]:
        """
        Fetch all test cases matching the configuration filters.
        
        Returns:
            List of TestCase objects ready for evaluation
        """
        test_cases = []
        conn = self._get_connection()
        
        try:
            for format_name in self.config.filters.formats:
                query, params = self._build_query(format_name)
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                for row in cursor.fetchall():
                    (question_id, passage_id, question_type_id, question_text,
                     expected_answer, verified, num_measures, fmt) = row
                    
                    # Get passage file path and content
                    passage_path = self._get_passage_path(passage_id, format_name)
                    passage_content = self._load_passage_content(passage_path)
                    
                    test_case = TestCase(
                        question_id=question_id,
                        passage_id=passage_id,
                        format=format_name,
                        question_text=question_text,
                        question_type_id=question_type_id,
                        expected_answer=str(expected_answer),
                        passage_content=passage_content,
                        passage_file_path=str(passage_path),
                        num_measures=num_measures,
                        verified=bool(verified),
                    )
                    test_cases.append(test_case)
        
        finally:
            conn.close()
        
        return test_cases
    
    def iterate_test_cases(self) -> Iterator[TestCase]:
        """
        Iterator version for memory efficiency with large datasets.
        """
        yield from self.fetch_test_cases()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics about matching test cases.
        
        Useful for validation before running full benchmark.
        """
        test_cases = self.fetch_test_cases()
        
        # Group by format
        by_format = {}
        for tc in test_cases:
            by_format.setdefault(tc.format, []).append(tc)
        
        # Group by question type
        by_type = {}
        for tc in test_cases:
            by_type.setdefault(tc.question_type_id, []).append(tc)
        
        # Group by num_measures
        by_measures = {}
        for tc in test_cases:
            by_measures.setdefault(tc.num_measures, []).append(tc)
        
        return {
            "total": len(test_cases),
            "by_format": {fmt: len(cases) for fmt, cases in by_format.items()},
            "by_question_type": {qt: len(cases) for qt, cases in by_type.items()},
            "by_num_measures": {nm: len(cases) for nm, cases in by_measures.items()},
            "verified_count": sum(1 for tc in test_cases if tc.verified),
        }


def build_prompt(
    test_case: TestCase,
    system_prompt: str,
    include_format_hint: bool = True,
) -> str:
    """
    Build the full prompt for a test case.
    
    Args:
        test_case: TestCase object
        system_prompt: System prompt text
        include_format_hint: Whether to add format hint
        
    Returns:
        Complete prompt string
    """
    format_hint = ""
    if include_format_hint:
        format_map = {
            "abc": "ABC notation",
            "humdrum": "Humdrum **kern notation",
            "mei": "MEI (Music Encoding Initiative) XML",
            "musicxml": "MusicXML",
        }
        format_name = format_map.get(test_case.format, test_case.format.upper())
        format_hint = f"\n[Note: This passage is encoded in {format_name}]"
    
    prompt = (
        f"Passage:\n{test_case.passage_content}\n\n"
        f"Question: {test_case.question_text}{format_hint}\n"
    )
    
    return prompt

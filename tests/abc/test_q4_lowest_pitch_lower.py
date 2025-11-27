"""
Tests for Q4 ABC extractor: Lowest pitch in lower staff.

Question: What is the lowest pitch in the lower staff?
Use scientific pitch notation (use 'b' for flats, '#' for sharps).
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from answer_extraction.abc.q4_lowest_pitch_lower import extract
from tests.conftest import get_verified_answers, get_passage_path, compare_answers


class TestQ4LowestPitchLower:
    """Test suite for ABC Q4 extractor."""
    
    FORMAT = "abc"
    QUESTION_TYPE_ID = 4
    
    @pytest.fixture
    def verified_answers(self):
        """Get all verified answers for this question type."""
        return get_verified_answers(self.FORMAT, self.QUESTION_TYPE_ID)
    
    def test_all_verified_passages(self, verified_answers):
        """Test extractor against all verified passages."""
        failures = []
        
        for passage_id, expected in verified_answers:
            file_path = get_passage_path(passage_id, self.FORMAT)
            
            if not file_path.exists():
                failures.append(f"{passage_id}: File not found")
                continue
            
            try:
                actual = extract(str(file_path))
                if not compare_answers(expected, actual):
                    failures.append(
                        f"{passage_id}: expected={expected}, got={actual}"
                    )
            except Exception as e:
                failures.append(f"{passage_id}: Error - {e}")
        
        if failures:
            pytest.fail(
                f"Failed {len(failures)}/{len(verified_answers)} passages:\n" +
                "\n".join(failures)
            )
    
    @pytest.mark.parametrize("passage_id", [
        "P-001", "P-002", "P-003", "P-004", "P-005",
        "P-006", "P-007", "P-008", "P-009", "P-010",
        "P-011", "P-012", "P-013", "P-014", "P-015",
        "P-016", "P-017", "P-018", "P-019", "P-020",
        "P-021", "P-022", "P-023", "P-024", "P-025",
        "P-026", "P-027", "P-028", "P-029", "P-030",
        "P-031", "P-032", "P-033", "P-034", "P-035",
        "P-036", "P-037", "P-038", "P-039", "P-040",
        "P-041", "P-042", "P-043", "P-044", "P-045",
    ])
    def test_individual_passage(self, passage_id):
        """Test a single passage."""
        answers = get_verified_answers(self.FORMAT, self.QUESTION_TYPE_ID, [passage_id])
        
        if not answers:
            pytest.skip(f"No verified answer for {passage_id}")
        
        expected = answers[0][1]
        file_path = get_passage_path(passage_id, self.FORMAT)
        
        assert file_path.exists(), f"File not found: {file_path}"
        
        actual = extract(str(file_path))
        assert compare_answers(expected, actual), \
            f"Expected {expected}, got {actual}"

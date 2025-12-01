"""
Unified tests for all answer extractors across all formats.

This module provides comprehensive testing for all question extractors
across all supported notation formats (ABC, Humdrum, MEI, MusicXML).

Tests are parameterized by (format, question_type_id) and run against
all verified answers in the database.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tests.conftest import get_verified_answers, get_passage_path, compare_answers

# Import all extractors
from answer_extraction.abc import (
    q1_note_count_lower as abc_q1,
    q2_note_count_upper as abc_q2,
    q3_first_pitch_upper as abc_q3,
    q4_lowest_pitch_lower as abc_q4,
    q5_longest_duration as abc_q5,
    q6_pitch_class_count as abc_q6,
    q7_interval_first_last as abc_q7,
    q8_rest_count as abc_q8,
    q9_first_note_duration as abc_q9,
)
from answer_extraction.humdrum import (
    q1_note_count_lower as hum_q1,
    q2_note_count_upper as hum_q2,
    q3_first_pitch_upper as hum_q3,
    q4_lowest_pitch_lower as hum_q4,
    q5_longest_duration as hum_q5,
    q6_pitch_class_count as hum_q6,
    q7_interval_first_last as hum_q7,
    q8_rest_count as hum_q8,
    q9_first_note_duration as hum_q9,
)
from answer_extraction.mei import (
    q1_note_count_lower as mei_q1,
    q2_note_count_upper as mei_q2,
    q3_first_pitch_upper as mei_q3,
    q4_lowest_pitch_lower as mei_q4,
    q5_longest_duration as mei_q5,
    q6_pitch_class_count as mei_q6,
    q7_interval_first_last as mei_q7,
    q8_rest_count as mei_q8,
    q9_first_note_duration as mei_q9,
)
from answer_extraction.musicxml import (
    q1_note_count_lower as mxml_q1,
    q2_note_count_upper as mxml_q2,
    q3_first_pitch_upper as mxml_q3,
    q4_lowest_pitch_lower as mxml_q4,
    q5_longest_duration as mxml_q5,
    q6_pitch_class_count as mxml_q6,
    q7_interval_first_last as mxml_q7,
    q8_rest_count as mxml_q8,
    q9_first_note_duration as mxml_q9,
)

# Extractor lookup table: (format, question_id) -> extract function
EXTRACTORS = {
    # ABC
    ('abc', 1): abc_q1.extract,
    ('abc', 2): abc_q2.extract,
    ('abc', 3): abc_q3.extract,
    ('abc', 4): abc_q4.extract,
    ('abc', 5): abc_q5.extract,
    ('abc', 6): abc_q6.extract,
    ('abc', 7): abc_q7.extract,
    ('abc', 8): abc_q8.extract,
    ('abc', 9): abc_q9.extract,
    # Humdrum
    ('humdrum', 1): hum_q1.extract,
    ('humdrum', 2): hum_q2.extract,
    ('humdrum', 3): hum_q3.extract,
    ('humdrum', 4): hum_q4.extract,
    ('humdrum', 5): hum_q5.extract,
    ('humdrum', 6): hum_q6.extract,
    ('humdrum', 7): hum_q7.extract,
    ('humdrum', 8): hum_q8.extract,
    ('humdrum', 9): hum_q9.extract,
    # MEI
    ('mei', 1): mei_q1.extract,
    ('mei', 2): mei_q2.extract,
    ('mei', 3): mei_q3.extract,
    ('mei', 4): mei_q4.extract,
    ('mei', 5): mei_q5.extract,
    ('mei', 6): mei_q6.extract,
    ('mei', 7): mei_q7.extract,
    ('mei', 8): mei_q8.extract,
    ('mei', 9): mei_q9.extract,
    # MusicXML
    ('musicxml', 1): mxml_q1.extract,
    ('musicxml', 2): mxml_q2.extract,
    ('musicxml', 3): mxml_q3.extract,
    ('musicxml', 4): mxml_q4.extract,
    ('musicxml', 5): mxml_q5.extract,
    ('musicxml', 6): mxml_q6.extract,
    ('musicxml', 7): mxml_q7.extract,
    ('musicxml', 8): mxml_q8.extract,
    ('musicxml', 9): mxml_q9.extract,
}

# Question descriptions for readable test output
QUESTION_NAMES = {
    1: "note_count_lower",
    2: "note_count_upper", 
    3: "first_pitch_upper",
    4: "lowest_pitch_lower",
    5: "longest_duration",
    6: "pitch_class_count",
    7: "interval_first_last",
    8: "rest_count",
    9: "first_note_duration",
}

# All format/question combinations with readable IDs
ALL_COMBINATIONS = [
    pytest.param(fmt, qid, id=f"{fmt}_Q{qid}_{QUESTION_NAMES[qid]}")
    for fmt in ['abc', 'humdrum', 'mei', 'musicxml']
    for qid in range(1, 10)
]


class TestAllExtractors:
    """Test all extractors against verified database answers."""
    
    @pytest.mark.parametrize("format_name,question_id", ALL_COMBINATIONS)
    def test_extractor(self, format_name, question_id):
        """
        Test an extractor against all verified answers.
        
        This is the main test that validates each extractor produces
        correct output for all passages with verified ground truth.
        """
        extractor = EXTRACTORS.get((format_name, question_id))
        if extractor is None:
            pytest.skip(f"No extractor for {format_name} Q{question_id}")
        
        verified = get_verified_answers(format_name, question_id)
        if not verified:
            pytest.skip(f"No verified answers for {format_name} Q{question_id}")
        
        failures = []
        for passage_id, expected in verified:
            file_path = get_passage_path(passage_id, format_name)
            
            if not file_path.exists():
                failures.append(f"{passage_id}: File not found at {file_path}")
                continue
            
            try:
                actual = extractor(str(file_path))
                if not compare_answers(expected, actual):
                    failures.append(f"{passage_id}: expected={expected}, got={actual}")
            except Exception as e:
                failures.append(f"{passage_id}: Error - {type(e).__name__}: {e}")
        
        if failures:
            pytest.fail(
                f"{format_name} Q{question_id} ({QUESTION_NAMES[question_id]}) - "
                f"Failed {len(failures)}/{len(verified)} passages:\n" +
                "\n".join(failures[:10])  # Limit output
            )


class TestCrossFormatConsistency:
    """Test that extractors produce consistent results across formats."""
    
    @pytest.mark.parametrize("question_id", range(1, 10))
    def test_cross_format_agreement(self, question_id):
        """
        Check if all formats agree on answers for the same passages.
        
        This helps identify encoding differences vs extractor bugs.
        Note: Some disagreements are expected due to format differences.
        """
        formats = ['abc', 'humdrum', 'mei', 'musicxml']
        
        # Get all verified answers per format
        answers_by_format = {}
        for fmt in formats:
            answers = get_verified_answers(fmt, question_id)
            answers_by_format[fmt] = {pid: ans for pid, ans in answers}
        
        # Find common passages
        common_passages = set.intersection(*[
            set(answers_by_format[fmt].keys()) for fmt in formats
        ])
        
        if not common_passages:
            pytest.skip(f"No passages with verified answers in all formats for Q{question_id}")
        
        # Check agreement
        disagreements = []
        for pid in sorted(common_passages):
            values = {fmt: answers_by_format[fmt][pid] for fmt in formats}
            unique_values = set(values.values())
            if len(unique_values) > 1:
                disagreements.append(f"{pid}: {values}")
        
        # Report but don't fail - disagreements may be legitimate encoding differences
        if disagreements:
            print(f"\nQ{question_id} format disagreements ({len(disagreements)}/{len(common_passages)}):")
            for d in disagreements[:5]:
                print(f"  {d}")

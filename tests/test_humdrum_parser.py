"""
Test suite for Humdrum parser using verified answers from the database.

This test file uses the 72 verified Humdrum answers as ground truth
to validate the parser implementation.
"""

import json
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from parsers.humdrum_parser import HumdrumParser
from core.extract_passage import extract


# Load verified test cases
TEST_DATA_PATH = Path(__file__).parent / 'verified_answers_humdrum.json'
with open(TEST_DATA_PATH) as f:
    TEST_CASES = json.load(f)


class TestHumdrumParser:
    """Test Humdrum parser against verified answers."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return HumdrumParser()
    
    @pytest.fixture
    def get_passage(self):
        """Helper to extract passage text."""
        def _extract(test_case):
            sonata = test_case['sonata_number']
            movement = test_case['movement']
            start = test_case['start_measure']
            end = test_case['end_measure']
            
            file_path = f"data/humdrum/{sonata:02d}-{movement}.krn"
            return extract('humdrum', file_path, start, end)
        
        return _extract
    
    # Group test cases by question type for better organization
    
    def test_count_notes_left_hand(self, parser, get_passage):
        """Test: How many notes are in the left hand?"""
        test_cases = [tc for tc in TEST_CASES 
                     if 'left hand' in tc['question_text'] 
                     and 'How many notes' in tc['question_text']]
        
        passed = 0
        failed = []
        
        for tc in test_cases:
            passage = get_passage(tc)
            result = parser.count_notes(
                passage, 
                hand='left', 
                include_grace=True, 
                count_tied_once=True
            )
            
            if str(result) == tc['expected_answer']:
                passed += 1
            else:
                failed.append({
                    'question_id': tc['question_id'],
                    'passage_id': tc['passage_id'],
                    'expected': tc['expected_answer'],
                    'got': str(result)
                })
        
        print(f"\n✓ Passed: {passed}/{len(test_cases)}")
        if failed:
            print("✗ Failed cases:")
            for f in failed:
                print(f"  Q-{f['question_id']} ({f['passage_id']}): expected {f['expected']}, got {f['got']}")
        
        assert len(failed) == 0, f"Failed {len(failed)} test cases"
    
    def test_count_notes_right_hand(self, parser, get_passage):
        """Test: How many notes are in the right hand?"""
        test_cases = [tc for tc in TEST_CASES 
                     if 'right hand' in tc['question_text'] 
                     and 'How many notes' in tc['question_text']]
        
        passed = 0
        failed = []
        
        for tc in test_cases:
            passage = get_passage(tc)
            result = parser.count_notes(
                passage, 
                hand='right', 
                include_grace=True, 
                count_tied_once=True
            )
            
            if str(result) == tc['expected_answer']:
                passed += 1
            else:
                failed.append({
                    'question_id': tc['question_id'],
                    'passage_id': tc['passage_id'],
                    'expected': tc['expected_answer'],
                    'got': str(result)
                })
        
        print(f"\n✓ Passed: {passed}/{len(test_cases)}")
        if failed:
            print("✗ Failed cases:")
            for f in failed:
                print(f"  Q-{f['question_id']} ({f['passage_id']}): expected {f['expected']}, got {f['got']}")
        
        assert len(failed) == 0, f"Failed {len(failed)} test cases"
    
    def test_count_rests(self, parser, get_passage):
        """Test: How many rests are in this measure?"""
        test_cases = [tc for tc in TEST_CASES if 'rests' in tc['question_text']]
        
        passed = 0
        failed = []
        
        for tc in test_cases:
            passage = get_passage(tc)
            result = parser.count_rests(passage)
            
            if str(result) == tc['expected_answer']:
                passed += 1
            else:
                failed.append({
                    'question_id': tc['question_id'],
                    'passage_id': tc['passage_id'],
                    'expected': tc['expected_answer'],
                    'got': str(result)
                })
        
        print(f"\n✓ Passed: {passed}/{len(test_cases)}")
        if failed:
            print("✗ Failed cases:")
            for f in failed:
                print(f"  Q-{f['question_id']} ({f['passage_id']}): expected {f['expected']}, got {f['got']}")
        
        assert len(failed) == 0, f"Failed {len(failed)} test cases"
    
    def test_count_pitch_classes(self, parser, get_passage):
        """Test: How many different pitch classes in left hand?"""
        test_cases = [tc for tc in TEST_CASES if 'pitch classes' in tc['question_text']]
        
        passed = 0
        failed = []
        
        for tc in test_cases:
            passage = get_passage(tc)
            result = parser.count_pitch_classes(passage, hand='left')
            
            if str(result) == tc['expected_answer']:
                passed += 1
            else:
                failed.append({
                    'question_id': tc['question_id'],
                    'passage_id': tc['passage_id'],
                    'expected': tc['expected_answer'],
                    'got': str(result)
                })
        
        print(f"\n✓ Passed: {passed}/{len(test_cases)}")
        if failed:
            print("✗ Failed cases:")
            for f in failed:
                print(f"  Q-{f['question_id']} ({f['passage_id']}): expected {f['expected']}, got {f['got']}")
        
        assert len(failed) == 0, f"Failed {len(failed)} test cases"
    
    def test_lowest_pitch_left_hand(self, parser, get_passage):
        """Test: What is the pitch of the lowest note in the left hand?"""
        test_cases = [tc for tc in TEST_CASES 
                     if 'lowest' in tc['question_text'] and 'left hand' in tc['question_text']]
        
        passed = 0
        failed = []
        
        for tc in test_cases:
            passage = get_passage(tc)
            result = parser.get_lowest_pitch(passage, hand='left', include_octave=True)
            
            if result == tc['expected_answer']:
                passed += 1
            else:
                failed.append({
                    'question_id': tc['question_id'],
                    'passage_id': tc['passage_id'],
                    'expected': tc['expected_answer'],
                    'got': result
                })
        
        print(f"\n✓ Passed: {passed}/{len(test_cases)}")
        if failed:
            print("✗ Failed cases:")
            for f in failed:
                print(f"  Q-{f['question_id']} ({f['passage_id']}): expected {f['expected']}, got {f['got']}")
        
        assert len(failed) == 0, f"Failed {len(failed)} test cases"
    
    def test_first_pitch_right_hand(self, parser, get_passage):
        """Test: What is the pitch of the first note in the right hand?"""
        test_cases = [tc for tc in TEST_CASES 
                     if 'first note' in tc['question_text'] 
                     and 'right hand' in tc['question_text']
                     and 'pitch' in tc['question_text']]
        
        passed = 0
        failed = []
        
        for tc in test_cases:
            passage = get_passage(tc)
            result = parser.get_first_pitch(passage, hand='right', include_octave=True)
            
            if result == tc['expected_answer']:
                passed += 1
            else:
                failed.append({
                    'question_id': tc['question_id'],
                    'passage_id': tc['passage_id'],
                    'expected': tc['expected_answer'],
                    'got': result
                })
        
        print(f"\n✓ Passed: {passed}/{len(test_cases)}")
        if failed:
            print("✗ Failed cases:")
            for f in failed:
                print(f"  Q-{f['question_id']} ({f['passage_id']}): expected {f['expected']}, got {f['got']}")
        
        assert len(failed) == 0, f"Failed {len(failed)} test cases"
    
    def test_longest_note_duration(self, parser, get_passage):
        """Test: What is the duration of the longest note?"""
        test_cases = [tc for tc in TEST_CASES if 'longest note' in tc['question_text']]
        
        passed = 0
        failed = []
        
        for tc in test_cases:
            passage = get_passage(tc)
            result = parser.get_longest_note_duration(passage, as_text=False)
            
            if result == tc['expected_answer']:
                passed += 1
            else:
                failed.append({
                    'question_id': tc['question_id'],
                    'passage_id': tc['passage_id'],
                    'expected': tc['expected_answer'],
                    'got': result
                })
        
        print(f"\n✓ Passed: {passed}/{len(test_cases)}")
        if failed:
            print("✗ Failed cases:")
            for f in failed:
                print(f"  Q-{f['question_id']} ({f['passage_id']}): expected {f['expected']}, got {f['got']}")
        
        assert len(failed) == 0, f"Failed {len(failed)} test cases"
    
    def test_first_note_duration_left_hand(self, parser, get_passage):
        """Test: What is the duration of the first note in the left hand?"""
        test_cases = [tc for tc in TEST_CASES 
                     if 'duration' in tc['question_text'] 
                     and 'first note' in tc['question_text']
                     and 'left hand' in tc['question_text']]
        
        passed = 0
        failed = []
        
        for tc in test_cases:
            passage = get_passage(tc)
            result = parser.get_first_note_duration(passage, hand='left', as_text=True)
            
            if result == tc['expected_answer']:
                passed += 1
            else:
                failed.append({
                    'question_id': tc['question_id'],
                    'passage_id': tc['passage_id'],
                    'expected': tc['expected_answer'],
                    'got': result
                })
        
        print(f"\n✓ Passed: {passed}/{len(test_cases)}")
        if failed:
            print("✗ Failed cases:")
            for f in failed:
                print(f"  Q-{f['question_id']} ({f['passage_id']}): expected {f['expected']}, got {f['got']}")
        
        assert len(failed) == 0, f"Failed {len(failed)} test cases"
    
    def test_interval_calculation(self, parser, get_passage):
        """Test: What is the interval between first and last notes?"""
        test_cases = [tc for tc in TEST_CASES if 'interval' in tc['question_text']]
        
        passed = 0
        failed = []
        
        for tc in test_cases:
            passage = get_passage(tc)
            result = parser.calculate_interval(passage, hand='right')
            
            if str(result) == tc['expected_answer']:
                passed += 1
            else:
                failed.append({
                    'question_id': tc['question_id'],
                    'passage_id': tc['passage_id'],
                    'expected': tc['expected_answer'],
                    'got': str(result)
                })
        
        print(f"\n✓ Passed: {passed}/{len(test_cases)}")
        if failed:
            print("✗ Failed cases:")
            for f in failed:
                print(f"  Q-{f['question_id']} ({f['passage_id']}): expected {f['expected']}, got {f['got']}")
        
        assert len(failed) == 0, f"Failed {len(failed)} test cases"


if __name__ == '__main__':
    # Run tests with verbose output
    pytest.main([__file__, '-v', '-s'])

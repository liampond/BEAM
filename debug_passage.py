#!/usr/bin/env python3
"""Debug script to examine specific passages."""

import sys
sys.path.insert(0, 'src')

from parsers.humdrum_parser import HumdrumParser

def extract_measure(file_path, measure_num):
    """Extract a single measure from a Humdrum file."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find the spine definition line
    spine_line_idx = None
    for i, line in enumerate(lines):
        if line.startswith('**'):
            spine_line_idx = i
            break
    
    if spine_line_idx is None:
        return None
    
    # Start from spine definitions
    measure_start_idx = None
    measure_end_idx = None
    
    for i in range(spine_line_idx, len(lines)):
        if lines[i].startswith(f'={measure_num}\t') or lines[i].startswith(f'={measure_num} '):
            measure_start_idx = i
        elif measure_start_idx and lines[i].startswith('='):
            measure_end_idx = i
            break
    
    if not measure_start_idx:
        return None
    
    # Include spine definitions and all interpretations before the measure
    result_lines = [lines[spine_line_idx]]
    
    # Add interpretations from before the measure
    for i in range(spine_line_idx + 1, measure_start_idx):
        if lines[i].startswith('*'):
            result_lines.append(lines[i])
    
    # Add the measure itself
    for i in range(measure_start_idx, measure_end_idx if measure_end_idx else len(lines)):
        result_lines.append(lines[i])
    
    return ''.join(result_lines)

def debug_passage(file_path, measure_num, passage_id, expected_left=None, expected_right=None, expected_rests=None):
    """Debug a specific passage."""
    parser = HumdrumParser()
    passage = extract_measure(file_path, measure_num)
    
    if not passage:
        print(f"Measure {measure_num} not found in {file_path}")
        return
    
    print(f"\n=== Debugging {passage_id} (Measure {measure_num}) ===")
    print("\nPassage text:")
    print(passage)
    print("\n" + "="*50)
    
    # Parse and show notes
    left_notes, right_notes = parser.parse_passage(passage)
    
    print(f"\nLeft hand notes ({len(left_notes)} total):")
    for i, note in enumerate(left_notes):
        print(f"  {i+1}. {note.pitch if not note.is_rest else 'REST'} "
              f"dur={note.duration} pos={note.position} "
              f"grace={note.is_grace} tied_cont={note.is_tied_continuation}")
    
    print(f"\nRight hand notes ({len(right_notes)} total):")
    for i, note in enumerate(right_notes):
        print(f"  {i+1}. {note.pitch if not note.is_rest else 'REST'} "
              f"dur={note.duration} pos={note.position} "
              f"grace={note.is_grace} tied_cont={note.is_tied_continuation}")
    
    # Count metrics
    left_count = parser.count_notes(passage, hand='left', include_grace=True, count_tied_once=True)
    right_count = parser.count_notes(passage, hand='right', include_grace=True, count_tied_once=True)
    rest_count = parser.count_rests(passage)
    
    print(f"\n=== Counts ===")
    print(f"Left hand notes: {left_count} (expected: {expected_left})")
    print(f"Right hand notes: {right_count} (expected: {expected_right})")
    print(f"Rests: {rest_count} (expected: {expected_rests})")

if __name__ == '__main__':
    # Debug the failing passages
    print("\n" + "="*70)
    print("DEBUGGING P-004 (Sonata 4, mvmt 3, measure 56)")
    print("="*70)
    debug_passage('data/humdrum/04-3.krn', 56, 'P-004', expected_left=5, expected_right=4)
    
    print("\n" + "="*70)
    print("DEBUGGING P-008 (Sonata 8, mvmt 1, measure 37)")
    print("="*70)
    debug_passage('data/humdrum/08-1.krn', 37, 'P-008', expected_rests=1)

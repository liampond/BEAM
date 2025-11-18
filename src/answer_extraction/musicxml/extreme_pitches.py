"""
Extreme Pitches - MusicXML Extractor

Finds the highest or lowest pitch in the specified staff.

Rules:
    - Collect all pitches in the staff
    - Compare using MIDI numbers
    - Return highest or lowest as requested
    
Question Pattern:
    "What is the pitch of the [highest/lowest] note in the [upper/lower] staff?"
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.answer_extraction.musicxml import _helpers
from src.db_utils import get_connection


def extract_answer(file_path: str, passage_id: str, extremum: str, staff: str = "upper") -> str:
    """
    Get highest or lowest pitch in the specified staff.
    
    Args:
        file_path: Path to MusicXML file
        passage_id: Passage ID to look up measure range (e.g., 'P-001')
        extremum: "highest" or "lowest"
        staff: "upper" or "lower"
    
    Returns:
        Pitch string (e.g., "C#5", "Bb3")
    
    Raises:
        ValueError: If passage not found, no notes in staff, or no measure range for MusicXML
    """
    # Validate extremum parameter
    if extremum.lower() not in ['highest', 'lowest']:
        raise ValueError(f"Invalid extremum: {extremum}. Must be 'highest' or 'lowest'")
    
    # Get format-specific measure range from database
    conn = get_connection()
    result = conn.execute("""
        SELECT start_measure, end_measure 
        FROM passage_measures 
        WHERE passage_id = ? AND format = 'musicxml'
    """, (passage_id,)).fetchone()
    
    if not result:
        raise ValueError(f"No measure range found for {passage_id} in MusicXML format")
    
    start_measure, end_measure = result
    
    # Parse MusicXML
    root = _helpers.parse_musicxml(file_path)
    
    # Determine staff number (1 = upper, 2 = lower)
    staff_num = 1 if staff.lower() == "upper" else 2
    
    # Get all notes in range for this staff
    all_notes = _helpers.get_notes_in_range(root, start_measure, end_measure, staff_num)
    
    # Collect all pitches (exclude rests, tied continuations, invisible notes)
    pitches = []
    for note in all_notes:
        if _helpers.is_rest(note):
            continue
        if _helpers.is_tied_continuation(note):
            continue
        if _helpers.is_invisible_note(note):
            continue
        
        pitch = _helpers.get_pitch(note)
        if pitch is not None:
            pitches.append(pitch)
    
    if not pitches:
        raise ValueError(f"No valid pitches found in {staff} staff for passage {passage_id}")
    
    # Find extreme pitch
    if extremum.lower() == "highest":
        extreme_pitch = max(pitches, key=_helpers.pitch_to_midi)
    else:  # lowest
        extreme_pitch = min(pitches, key=_helpers.pitch_to_midi)
    
    return extreme_pitch


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) >= 5:
        answer = extract_answer(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
        print(answer)
    else:
        print("Usage: python extreme_pitches.py <file_path> <passage_id> <extremum> <staff>")
        print("Example: python extreme_pitches.py data/musicxml/16-1.xml P-001 highest upper")

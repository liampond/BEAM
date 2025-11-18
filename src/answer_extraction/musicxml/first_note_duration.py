"""
First Note Duration - MusicXML Extractor

Finds the duration of the first note in the specified staff.
If multiple notes occur simultaneously, chooses the highest pitch.
Returns duration as a named value (e.g., "Dotted eighth note").

Rules:
    - Find chronologically first note(s)
    - If multiple simultaneous notes, select highest pitch
    - Exclude rests, tied continuations, invisible notes
    - Return as named duration
    
Question Pattern:
    "What is the duration of the first note in the [upper/lower] staff? 
     If there are multiple simultaneous occurrences, choose the highest note. 
     Respond with a note value (e.g., Dotted eighth note)."
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.answer_extraction.musicxml import _helpers
from src.answer_extraction.musicxml import first_note_pitch
from src.core.db_utils import get_connection


def extract_answer(file_path: str, passage_id: str, staff: str = "upper") -> str:
    """
    Get duration of first note in the specified staff as named value.
    If multiple simultaneous notes, choose highest pitch.
    
    Args:
        file_path: Path to MusicXML file
        passage_id: Passage ID to look up measure range (e.g., 'P-001')
        staff: "upper" or "lower"
    
    Returns:
        Duration name (e.g., "Quarter note", "Dotted eighth note")
    
    Raises:
        ValueError: If passage not found, no notes in staff, or no measure range for MusicXML
    """
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
    
    # Filter valid notes (exclude rests, tied continuations, invisible notes)
    valid_notes = []
    for note in all_notes:
        if _helpers.is_rest(note):
            continue
        if _helpers.is_tied_continuation(note):
            continue
        if _helpers.is_invisible_note(note):
            continue
        valid_notes.append(note)
    
    if not valid_notes:
        raise ValueError(f"No valid notes found in {staff} staff for passage {passage_id}")
    
    # Get first note(s) - handles simultaneous notes
    first_notes = first_note_pitch.get_first_notes(valid_notes)
    
    # If only one note, return its duration
    if len(first_notes) == 1:
        beats = _helpers.get_duration_in_beats(first_notes[0])
        return _helpers.duration_to_note_name(beats)
    
    # Multiple simultaneous notes - choose highest pitch, return its duration
    highest_note = None
    highest_midi = -1
    
    for note in first_notes:
        pitch = _helpers.get_pitch(note)
        if pitch is not None:
            midi = _helpers.pitch_to_midi(pitch)
            if midi > highest_midi:
                highest_midi = midi
                highest_note = note
    
    if highest_note is None:
        raise ValueError(f"No valid pitches found in first notes")
    
    beats = _helpers.get_duration_in_beats(highest_note)
    return _helpers.duration_to_note_name(beats)


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) >= 4:
        answer = extract_answer(sys.argv[1], sys.argv[2], sys.argv[3])
        print(answer)
    else:
        print("Usage: python first_note_duration.py <file_path> <passage_id> <staff>")
        print("Example: python first_note_duration.py data/musicxml/16-1.xml P-001 lower")

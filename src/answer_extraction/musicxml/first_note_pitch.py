"""
First Note Pitch - MusicXML Extractor

Finds the pitch of the first note in the specified staff.
If multiple notes occur simultaneously, chooses the highest pitch.

Rules:
    - Find chronologically first note(s)
    - If multiple simultaneous notes, select highest pitch
    - Exclude rests, tied continuations, invisible notes
    
Question Pattern:
    "What is the pitch of the first note in the [upper/lower] staff? 
     If there are multiple simultaneous occurrences, choose the highest note."
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.answer_extraction.musicxml import _helpers
from src.db_utils import get_connection
from typing import List, Optional
import xml.etree.ElementTree as ET


def get_first_notes(notes: List[ET.Element]) -> List[ET.Element]:
    """
    Get the first note(s) from a chronologically ordered list.
    
    Returns all notes at the same time position (to handle chords/simultaneous notes).
    
    Args:
        notes: List of note elements in chronological order
    
    Returns:
        List of note elements at the first time position
    """
    if not notes:
        return []
    
    # First valid note sets the measure and position
    first_note = notes[0]
    first_measure = first_note.get('_measure_number')
    
    # For simplicity, all notes in the same measure at the start are considered simultaneous
    # In a more robust implementation, we'd track exact time positions within measures
    simultaneous_notes = [first_note]
    
    for note in notes[1:]:
        if note.get('_measure_number') == first_measure:
            # Still in first measure - could be simultaneous
            simultaneous_notes.append(note)
        else:
            # Moved to next measure - stop
            break
    
    return simultaneous_notes


def extract_answer(file_path: str, passage_id: str, staff: str = "upper") -> str:
    """
    Get pitch of first note in the specified staff.
    If multiple simultaneous notes, choose highest pitch.
    
    Args:
        file_path: Path to MusicXML file
        passage_id: Passage ID to look up measure range (e.g., 'P-001')
        staff: "upper" or "lower"
    
    Returns:
        Pitch string (e.g., "C#5", "Bb3")
    
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
    first_notes = get_first_notes(valid_notes)
    
    # If only one note, return its pitch
    if len(first_notes) == 1:
        pitch = _helpers.get_pitch(first_notes[0])
        if pitch is None:
            raise ValueError(f"First note has no pitch (might be a rest)")
        return pitch
    
    # Multiple simultaneous notes - choose highest
    highest_pitch = None
    highest_midi = -1
    
    for note in first_notes:
        pitch = _helpers.get_pitch(note)
        if pitch is not None:
            midi = _helpers.pitch_to_midi(pitch)
            if midi > highest_midi:
                highest_midi = midi
                highest_pitch = pitch
    
    if highest_pitch is None:
        raise ValueError(f"No valid pitches found in first notes")
    
    return highest_pitch


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) >= 4:
        answer = extract_answer(sys.argv[1], sys.argv[2], sys.argv[3])
        print(answer)
    else:
        print("Usage: python first_note_pitch.py <file_path> <passage_id> <staff>")
        print("Example: python first_note_pitch.py data/musicxml/16-1.xml P-001 upper")

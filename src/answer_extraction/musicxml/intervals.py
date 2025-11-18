"""
Intervals - MusicXML Extractor

Calculates the interval in semitones between the first and last notes of the specified staff.

Rules:
    - Get first note (if simultaneous, choose highest)
    - Get last note (if simultaneous, choose highest)
    - Calculate semitone distance using MIDI numbers
    
Question Pattern:
    "What is the interval in semitones between the first and last notes of the [upper/lower] staff?"
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.answer_extraction.musicxml import _helpers
from src.answer_extraction.musicxml import first_note_pitch
from src.db_utils import get_connection
from typing import List
import xml.etree.ElementTree as ET


def get_last_notes(notes: List[ET.Element]) -> List[ET.Element]:
    """
    Get the last note(s) from a chronologically ordered list.
    
    Returns all notes at the same time position (to handle chords/simultaneous notes).
    
    Args:
        notes: List of note elements in chronological order
    
    Returns:
        List of note elements at the last time position
    """
    if not notes:
        return []
    
    # Last valid note sets the measure and position
    last_note = notes[-1]
    last_measure = last_note.get('_measure_number')
    
    # Collect all notes in the last measure (working backwards)
    simultaneous_notes = [last_note]
    
    for note in reversed(notes[:-1]):
        if note.get('_measure_number') == last_measure:
            # Still in last measure - could be simultaneous
            simultaneous_notes.insert(0, note)
        else:
            # Moved to previous measure - stop
            break
    
    return simultaneous_notes


def extract_answer(file_path: str, passage_id: str, staff: str = "upper") -> str:
    """
    Calculate interval in semitones between first and last notes.
    If multiple simultaneous notes at either position, choose highest.
    
    Args:
        file_path: Path to MusicXML file
        passage_id: Passage ID to look up measure range (e.g., 'P-001')
        staff: "upper" or "lower"
    
    Returns:
        Interval in semitones as string (e.g., "7", "-5")
    
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
    
    if len(valid_notes) < 2:
        raise ValueError(f"Need at least 2 notes to calculate interval, found {len(valid_notes)}")
    
    # Get first note(s) - handles simultaneous notes
    first_notes = first_note_pitch.get_first_notes(valid_notes)
    last_notes = get_last_notes(valid_notes)
    
    # Get first pitch (highest if simultaneous)
    if len(first_notes) == 1:
        first_pitch = _helpers.get_pitch(first_notes[0])
    else:
        highest_midi = -1
        first_pitch = None
        for note in first_notes:
            pitch = _helpers.get_pitch(note)
            if pitch is not None:
                midi = _helpers.pitch_to_midi(pitch)
                if midi > highest_midi:
                    highest_midi = midi
                    first_pitch = pitch
    
    # Get last pitch (highest if simultaneous)
    if len(last_notes) == 1:
        last_pitch = _helpers.get_pitch(last_notes[0])
    else:
        highest_midi = -1
        last_pitch = None
        for note in last_notes:
            pitch = _helpers.get_pitch(note)
            if pitch is not None:
                midi = _helpers.pitch_to_midi(pitch)
                if midi > highest_midi:
                    highest_midi = midi
                    last_pitch = pitch
    
    if first_pitch is None or last_pitch is None:
        raise ValueError(f"Could not determine first or last pitch")
    
    # Calculate interval in semitones
    first_midi = _helpers.pitch_to_midi(first_pitch)
    last_midi = _helpers.pitch_to_midi(last_pitch)
    interval = last_midi - first_midi
    
    return str(interval)


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) >= 4:
        answer = extract_answer(sys.argv[1], sys.argv[2], sys.argv[3])
        print(answer)
    else:
        print("Usage: python intervals.py <file_path> <passage_id> <staff>")
        print("Example: python intervals.py data/musicxml/16-1.xml P-001 upper")

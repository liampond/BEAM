"""
Pitch Class Count - MusicXML Extractor

Counts the number of different pitch classes used in the specified staff.

Pitch class = note name without octave (e.g., C, C#, D, Eb, etc.)
Examples: C4 and C5 are the same pitch class (C)
          C# and Db are different pitch classes (enharmonic equivalents counted separately)

Rules:
    - Collect all pitches in staff
    - Extract pitch class (note name without octave)
    - Count unique pitch classes
    
Question Pattern:
    "How many different pitch classes are used in the [upper/lower] staff?"
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.answer_extraction.musicxml import _helpers
from src.core.db_utils import get_connection


def extract_answer(file_path: str, passage_id: str, staff: str = "upper") -> str:
    """
    Count unique pitch classes in the specified staff.
    
    Args:
        file_path: Path to MusicXML file
        passage_id: Passage ID to look up measure range (e.g., 'P-001')
        staff: "upper" or "lower"
    
    Returns:
        Count of unique pitch classes (e.g., "7")
    
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
    
    # Collect unique pitch classes
    pitch_classes = set()
    
    for note in all_notes:
        if _helpers.is_rest(note):
            continue
        if _helpers.is_tied_continuation(note):
            continue
        if _helpers.is_invisible_note(note):
            continue
        
        pitch = _helpers.get_pitch(note)
        if pitch is not None:
            pitch_class = _helpers.get_pitch_class(pitch)
            pitch_classes.add(pitch_class)
    
    return str(len(pitch_classes))


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) >= 4:
        answer = extract_answer(sys.argv[1], sys.argv[2], sys.argv[3])
        print(answer)
    else:
        print("Usage: python pitch_class_count.py <file_path> <passage_id> <staff>")
        print("Example: python pitch_class_count.py data/musicxml/16-1.xml P-001 upper")

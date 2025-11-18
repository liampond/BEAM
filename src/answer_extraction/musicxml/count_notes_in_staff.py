"""
Count Notes in Staff - MusicXML Extractor

Counts the number of notes in the specified staff (upper or lower).

Rules:
    - Include: Regular notes and grace notes
    - Exclude: Rests, tied continuations, invisible notes (print-object="no")
    
Question Pattern:
    "How many notes are in the [upper/lower] staff in this passage?"
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.answer_extraction.musicxml import _helpers
from src.core.db_utils import get_connection


def extract_answer(file_path: str, passage_id: str, staff: str = "upper") -> str:
    """
    Count notes in the specified staff.
    
    Args:
        file_path: Path to MusicXML file
        passage_id: Passage ID to look up measure range (e.g., 'P-001')
        staff: "upper" or "lower"
    
    Returns:
        String representation of count (e.g., "8")
    
    Raises:
        ValueError: If passage not found or no measure range for MusicXML
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
    notes = _helpers.get_notes_in_range(root, start_measure, end_measure, staff_num)
    
    # Count notes (exclude rests, include grace notes, exclude tied continuations, exclude invisible notes)
    count = 0
    for note in notes:
        if _helpers.is_rest(note):
            continue
        if _helpers.is_tied_continuation(note):
            continue
        if _helpers.is_invisible_note(note):
            continue
        count += 1
    
    return str(count)


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) >= 4:
        answer = extract_answer(sys.argv[1], sys.argv[2], sys.argv[3])
        print(answer)
    else:
        print("Usage: python count_notes_in_staff.py <file_path> <passage_id> <staff>")
        print("Example: python count_notes_in_staff.py data/musicxml/16-1.xml P-001 upper")

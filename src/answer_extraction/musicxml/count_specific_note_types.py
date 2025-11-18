"""
Count Specific Note Types - MusicXML Extractor

Counts notes of a specific duration type (e.g., sixteenth notes, half notes).

Rules:
    - Filter by <type> element (e.g., "16th", "half", "quarter")
    - Apply same exclusions as general note counting
    
Question Pattern:
    "How many [sixteenth/half/quarter/eighth/whole] notes appear in the [upper/lower] staff?"
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.answer_extraction.musicxml import _helpers
from src.core.db_utils import get_connection


# Map note type names to MusicXML <type> values
NOTE_TYPE_MAP = {
    'whole': 'whole',
    'half': 'half',
    'quarter': 'quarter',
    'eighth': 'eighth',
    'sixteenth': '16th',
    'thirty-second': '32nd',
    'sixty-fourth': '64th',
}


def extract_answer(file_path: str, passage_id: str, note_type: str, staff: str = "upper") -> str:
    """
    Count notes of specific type in the specified staff.
    
    Args:
        file_path: Path to MusicXML file
        passage_id: Passage ID to look up measure range (e.g., 'P-001')
        note_type: Type of note (e.g., 'sixteenth', 'half', 'quarter')
        staff: "upper" or "lower"
    
    Returns:
        String representation of count (e.g., "3")
    
    Raises:
        ValueError: If passage not found, unknown note type, or no measure range for MusicXML
    """
    # Validate and map note type
    note_type_lower = note_type.lower()
    if note_type_lower not in NOTE_TYPE_MAP:
        raise ValueError(f"Unknown note type: {note_type}. Valid types: {list(NOTE_TYPE_MAP.keys())}")
    
    musicxml_type = NOTE_TYPE_MAP[note_type_lower]
    
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
    
    # Count notes of specific type
    count = 0
    for note in notes:
        # Apply standard exclusions
        if _helpers.is_rest(note):
            continue
        if _helpers.is_tied_continuation(note):
            continue
        if _helpers.is_invisible_note(note):
            continue
        
        # Check if note type matches
        type_elem = note.find('type')
        if type_elem is not None and type_elem.text == musicxml_type:
            count += 1
    
    return str(count)


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) >= 5:
        answer = extract_answer(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
        print(answer)
    else:
        print("Usage: python count_specific_note_types.py <file_path> <passage_id> <note_type> <staff>")
        print("Example: python count_specific_note_types.py data/musicxml/16-1.xml P-001 sixteenth upper")

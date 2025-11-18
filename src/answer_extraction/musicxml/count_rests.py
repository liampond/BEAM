"""
Count Rests - MusicXML Extractor

Counts the total number of rests in the passage (all staves).

Rules:
    - Count any note element with <rest/> element
    - Include all rests regardless of staff
    
Question Pattern:
    "How many rests are in this passage?"
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.answer_extraction.musicxml import _helpers
from src.core.db_utils import get_connection


def extract_answer(file_path: str, passage_id: str) -> str:
    """
    Count rests in the passage (all staves).
    
    Args:
        file_path: Path to MusicXML file
        passage_id: Passage ID to look up measure range (e.g., 'P-001')
    
    Returns:
        String representation of count (e.g., "4")
    
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
    
    # Get all notes in range (all staves)
    notes = _helpers.get_notes_in_range(root, start_measure, end_measure, staff=None)
    
    # Count rests
    count = 0
    for note in notes:
        if _helpers.is_rest(note):
            # Don't count invisible rests (used for spacing)
            if not _helpers.is_invisible_note(note):
                count += 1
    
    return str(count)


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) >= 3:
        answer = extract_answer(sys.argv[1], sys.argv[2])
        print(answer)
    else:
        print("Usage: python count_rests.py <file_path> <passage_id>")
        print("Example: python count_rests.py data/musicxml/16-1.xml P-001")

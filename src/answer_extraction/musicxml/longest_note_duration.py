"""
Longest Note Duration - MusicXML Extractor

Finds the duration of the longest note in the passage (all staves).
Returns duration in beats, formatted as integer if whole number, decimal otherwise.

Rules:
    - Check all notes in passage (both staves)
    - Exclude rests, tied continuations, invisible notes
    - Return in beats: "2" not "2.0", but "1.5" for dotted notes
    
Question Pattern:
    "What is the duration of the longest note in this passage? 
     Respond in the number of beats. Use decimals only when necessary (e.g., 4, 2.25)."
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.answer_extraction.musicxml import _helpers
from src.core.db_utils import get_connection


def extract_answer(file_path: str, passage_id: str) -> str:
    """
    Get duration of longest note in the passage in beats.
    
    Args:
        file_path: Path to MusicXML file
        passage_id: Passage ID to look up measure range (e.g., 'P-001')
    
    Returns:
        Duration in beats (e.g., "2", "1.5", "4")
    
    Raises:
        ValueError: If passage not found, no notes in passage, or no measure range for MusicXML
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
    all_notes = _helpers.get_notes_in_range(root, start_measure, end_measure, staff=None)
    
    # Collect durations (exclude rests, tied continuations, invisible notes)
    durations = []
    for note in all_notes:
        if _helpers.is_rest(note):
            continue
        if _helpers.is_tied_continuation(note):
            continue
        if _helpers.is_invisible_note(note):
            continue
        
        beats = _helpers.get_duration_in_beats(note)
        if beats > 0:
            durations.append(beats)
    
    if not durations:
        raise ValueError(f"No valid notes found in passage {passage_id}")
    
    # Find longest duration
    longest_duration = max(durations)
    
    # Format: integer if whole number, decimal otherwise
    return _helpers.format_beats(longest_duration)


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) >= 3:
        answer = extract_answer(sys.argv[1], sys.argv[2])
        print(answer)
    else:
        print("Usage: python longest_note_duration.py <file_path> <passage_id>")
        print("Example: python longest_note_duration.py data/musicxml/16-1.xml P-001")

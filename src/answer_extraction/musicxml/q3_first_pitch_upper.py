"""
Q3: What is the pitch of the first note in the upper staff?

If there are multiple simultaneous notes, respond with the highest pitch.
Denote octave with scientific pitch notation (e.g., C4).
"""

from .utils import parse_musicxml_file, get_first_note_pitch, UPPER_STAFF
from ..registry import register_extractor


@register_extractor(3, "musicxml")
def extract(file_path: str) -> str:
    """
    Find the first note pitch in the upper staff (staff 1).
    
    In MusicXML, pitch is encoded with <pitch> containing:
    - <step>: pitch letter (C, D, E, F, G, A, B)
    - <alter>: chromatic alteration (-1, 0, 1, etc.)
    - <octave>: octave number
    
    Args:
        file_path: Path to the MusicXML (.xml) passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5"), or "N/A" if no notes
    """
    root = parse_musicxml_file(file_path)
    pitch = get_first_note_pitch(root, UPPER_STAFF)
    if pitch is None:
        return "N/A"
    return pitch

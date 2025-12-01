"""
Q3: What is the pitch of the first note in the upper staff?

If there are multiple simultaneous notes, respond with the highest pitch.
Denote octave with scientific pitch notation (e.g., C4).
"""

from .utils import parse_mei_file, get_first_note_pitch
from ..registry import register_extractor


@register_extractor(3, "mei")
def extract(file_path: str) -> str:
    """
    Find the first note pitch in the upper staff (staff 1).
    
    In MEI, pitch is encoded with @pname (pitch class) and @oct (octave).
    Accidentals may be in @accid or @accid.ges.
    
    Args:
        file_path: Path to the MEI (.mei) passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5"), or "N/A" if no notes
    """
    root = parse_mei_file(file_path)
    pitch = get_first_note_pitch(root, "1")
    if pitch is None:
        return "N/A"
    return pitch


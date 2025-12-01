"""
Q6: How many different pitch classes are used in the lower staff?

Consider pitch classes without regard to octave (i.e., all Cs are the same 
pitch class). Respond with a number (e.g., 5).
"""

from .utils import parse_mei_file, get_pitch_classes_in_staff, count_notes_in_staff
from ..registry import register_extractor


@register_extractor(6, "mei")
def extract(file_path: str) -> str:
    """
    Count distinct pitch classes in the lower staff (staff 2).
    
    Returns "N/A" if there are no notes in the lower staff (only rests).
    
    Args:
        file_path: Path to the MEI (.mei) passage file
    
    Returns:
        The count as a string, or "N/A" if no notes
    """
    root = parse_mei_file(file_path)
    
    # Check if there are any notes at all
    note_count = count_notes_in_staff(root, "2")
    if note_count == 0:
        return "N/A"
    
    pitch_classes = get_pitch_classes_in_staff(root, "2")
    return str(len(pitch_classes))



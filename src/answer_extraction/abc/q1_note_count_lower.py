"""
Q1: How many notes are in the lower staff in this passage?

Include grace notes and ornaments. Count tied notes only once.
Respond with a single number.
"""

from ..registry import register_extractor
from .utils import get_lower_staff_voices, count_notes_for_voices


@register_extractor(1, "abc")
def extract(file_path: str) -> str:
    """
    Count notes in the lower staff of an ABC notation file.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The count as a string
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Get voice(s) for the lower staff
    lower_voices = get_lower_staff_voices(content)
    
    # Count notes across all voices in the lower staff
    note_count = count_notes_for_voices(content, lower_voices)
    
    return str(note_count)

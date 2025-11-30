"""
Q2: How many notes are in the upper staff in this passage?

Include grace notes and ornaments. Count tied notes only once.
Respond with a single number.
"""

from ..registry import register_extractor
from .utils import get_upper_spine_data, count_notes_in_spine


@register_extractor(2, "humdrum")
def extract(file_path: str) -> str:
    """
    Count notes in the upper staff (rightmost **kern spine) of a Humdrum file.
    
    In Humdrum, spines are ordered left-to-right with the rightmost
    typically being the highest voice (treble/right hand).
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The count as a string
    """
    # Get data tokens from the upper (rightmost) kern spine
    upper_tokens = get_upper_spine_data(file_path)
    
    # Count notes, including grace notes, counting ties only once
    note_count = count_notes_in_spine(upper_tokens, include_grace=True)
    
    return str(note_count)

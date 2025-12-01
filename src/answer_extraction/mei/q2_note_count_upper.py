"""
Q2: How many notes are in the upper staff in this passage?

Include grace notes and ornaments. Count tied notes only once.
Respond with a single number.
"""

from .utils import count_upper_staff_notes
from ..registry import register_extractor


@register_extractor(2, "mei")
def extract(file_path: str) -> str:
    """
    Count notes in the upper staff (staff 1) of an MEI file.
    
    In MEI, staves are numbered with staff@n attribute.
    Staff 1 is typically the upper staff.
    
    Includes grace notes. Tied notes are counted only once 
    (the continuation notes are excluded).
    
    Args:
        file_path: Path to the MEI (.mei) passage file
    
    Returns:
        The count as a string
    """
    count = count_upper_staff_notes(file_path)
    return str(count)


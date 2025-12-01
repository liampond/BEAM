"""
Q1: How many notes are in the lower staff in this passage?

Include grace notes and ornaments. Count tied notes only once.
Respond with a single number.
"""

from .utils import count_lower_staff_notes
from ..registry import register_extractor


@register_extractor(1, "musicxml")
def extract(file_path: str) -> str:
    """
    Count notes in the lower staff (staff 2) of a MusicXML file.
    
    In MusicXML, staves are indicated by the <staff> element within <note>.
    Staff 1 is typically upper, staff 2 is lower.
    
    Includes grace notes. Tied notes are counted only once
    (the continuation notes are excluded).
    
    Args:
        file_path: Path to the MusicXML (.xml) passage file
    
    Returns:
        The count as a string
    """
    count = count_lower_staff_notes(file_path)
    return str(count)

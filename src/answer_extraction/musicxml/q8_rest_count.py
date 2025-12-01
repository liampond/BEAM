"""
Q8: How many rests are in this passage?

Respond with a number (e.g., 3).
"""

from .utils import parse_musicxml_file, count_rests_in_staff, UPPER_STAFF, LOWER_STAFF
from ..registry import register_extractor


@register_extractor(8, "musicxml")
def extract(file_path: str) -> str:
    """
    Count rests in a MusicXML file (both staves combined).
    
    In MusicXML, rests are <note> elements with a <rest/> child element.
    Only visible rests are counted.
    
    Args:
        file_path: Path to the MusicXML (.xml) passage file
    
    Returns:
        The count as a string
    """
    root = parse_musicxml_file(file_path)
    
    # Count rests in both staves
    upper_rests = count_rests_in_staff(root, UPPER_STAFF)
    lower_rests = count_rests_in_staff(root, LOWER_STAFF)
    
    return str(upper_rests + lower_rests)

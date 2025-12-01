"""
Q8: How many rests are in this passage?

Respond with a number (e.g., 3).
"""

from .utils import parse_mei_file, count_rests_in_staff
from ..registry import register_extractor


@register_extractor(8, "mei")
def extract(file_path: str) -> str:
    """
    Count rests in an MEI file (both staves combined).
    
    In MEI, rests are <rest> elements.
    
    Args:
        file_path: Path to the MEI (.mei) passage file
    
    Returns:
        The count as a string
    """
    root = parse_mei_file(file_path)
    
    # Count rests in both staves
    upper_rests = count_rests_in_staff(root, "1")
    lower_rests = count_rests_in_staff(root, "2")
    
    return str(upper_rests + lower_rests)


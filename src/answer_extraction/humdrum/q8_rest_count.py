"""
Q8: How many rests are in this passage?

Respond with a number (e.g., 3).
"""

from ..registry import register_extractor
from .utils import get_lower_spine_data, get_upper_spine_data, count_rests_in_spine


@register_extractor(8, "humdrum")
def extract(file_path: str) -> str:
    """
    Count rests in a Humdrum file (across both staves).
    
    In Humdrum, rests are indicated by 'r' with a duration prefix.
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The count as a string
    """
    lower_tokens = get_lower_spine_data(file_path)
    upper_tokens = get_upper_spine_data(file_path)
    
    lower_rests = count_rests_in_spine(lower_tokens)
    upper_rests = count_rests_in_spine(upper_tokens)
    
    return str(lower_rests + upper_rests)

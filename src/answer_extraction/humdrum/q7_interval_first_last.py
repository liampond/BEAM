"""
Q7: What is the interval between the first and last notes in the upper staff?

Respond with the number of semitones as a positive integer (e.g., 5 for a 
perfect fourth). Use the absolute value.
"""

from ..registry import register_extractor
from .utils import get_upper_spine_data_by_row, get_interval_first_last_by_rows


@register_extractor(7, "humdrum")
def extract(file_path: str) -> str:
    """
    Calculate interval between first and last notes in upper staff.
    
    Uses row-grouped data to correctly handle spine splits where
    simultaneous notes appear in different columns.
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The interval in semitones as a string (absolute value)
    """
    upper_rows = get_upper_spine_data_by_row(file_path)
    interval = get_interval_first_last_by_rows(upper_rows)
    
    if interval is None:
        return "N/A"
    
    # Return absolute value
    return str(abs(interval))

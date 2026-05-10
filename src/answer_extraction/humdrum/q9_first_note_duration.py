"""
Q9: What is the duration of the first note in the lower staff?

If there are multiple simultaneous notes, respond with the duration of the 
highest note. Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from ..registry import register_extractor
from .utils import get_lower_spine_data_by_row, get_first_note_duration_by_rows


@register_extractor(9, "humdrum")
def extract(file_path: str) -> str:
    """
    Find the duration of the first note in lower staff.

    Uses row-grouped spine data so that simultaneous notes across spine-split
    sub-spines are visible at the first event row; the highest-pitched note's
    duration is returned, matching the question wording.

    Args:
        file_path: Path to the Humdrum (.krn) passage file

    Returns:
        The duration in quarter notes as a string
    """
    rows = get_lower_spine_data_by_row(file_path)
    duration = get_first_note_duration_by_rows(rows)
    return duration if duration else "N/A"

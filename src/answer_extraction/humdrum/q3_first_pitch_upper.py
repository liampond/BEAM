"""
Q3: What is the pitch of the first note in the upper staff?

If there are multiple simultaneous notes, respond with the highest pitch.
Denote octave with scientific pitch notation (e.g., C4).
"""

from ..registry import register_extractor
from .utils import get_upper_spine_data_by_row, get_first_note_pitch_by_rows


@register_extractor(3, "humdrum")
def extract(file_path: str) -> str:
    """
    Find the first note pitch in the upper staff (rightmost **kern spine).

    Row-grouped extraction is required so spine splits (``*^``) at the
    start of a passage are handled correctly: simultaneous notes that fall
    in different sub-spine columns must all be considered when picking the
    highest. The flat-list version misses them.

    Grace notes are included per the question wording.
    """
    upper_rows = get_upper_spine_data_by_row(file_path)
    pitch = get_first_note_pitch_by_rows(upper_rows, return_highest_in_chord=True)
    return pitch if pitch else "N/A"

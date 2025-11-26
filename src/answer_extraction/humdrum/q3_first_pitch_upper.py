"""
Q3: What is the pitch of the first note in the upper staff?

If there are multiple simultaneous notes, respond with the highest pitch.
Denote octave with scientific pitch notation (e.g., C4).
"""

from ..registry import register_extractor


@register_extractor(3, "humdrum")
def extract(file_path: str) -> str:
    """
    Find the first note pitch in the upper staff (rightmost spine).
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5")
    """
    # TODO: Implement Humdrum parsing for first upper staff pitch
    raise NotImplementedError("Humdrum Q3 extractor not yet implemented")

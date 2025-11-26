"""
Q3: What is the pitch of the first note in the upper staff?

If there are multiple simultaneous notes, respond with the highest pitch.
Denote octave with scientific pitch notation (e.g., C4).
"""

from ..registry import register_extractor


@register_extractor(3, "abc")
def extract(file_path: str) -> str:
    """
    Find the first note pitch in the upper staff of an ABC notation file.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5")
    """
    # TODO: Implement ABC parsing for first upper staff pitch
    raise NotImplementedError("ABC Q3 extractor not yet implemented")

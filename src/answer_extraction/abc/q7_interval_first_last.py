"""
Q7: What is the interval between the first and last notes in the upper staff?

Respond with the number of semitones as a positive integer (e.g., 5 for a 
perfect fourth). Use the absolute value.
"""

from ..registry import register_extractor


@register_extractor(7, "abc")
def extract(file_path: str) -> str:
    """
    Calculate interval between first and last notes in upper staff.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The interval in semitones as a string
    """
    # TODO: Implement ABC parsing for upper staff interval
    raise NotImplementedError("ABC Q7 extractor not yet implemented")

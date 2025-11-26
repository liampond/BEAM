"""
Q9: What is the duration of the first note in the lower staff?

If there are multiple simultaneous notes, respond with the duration of the 
highest note. Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from ..registry import register_extractor


@register_extractor(9, "abc")
def extract(file_path: str) -> str:
    """
    Find the duration of the first note in lower staff.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The duration in quarter notes as a string
    """
    # TODO: Implement ABC parsing for first lower staff note duration
    raise NotImplementedError("ABC Q9 extractor not yet implemented")

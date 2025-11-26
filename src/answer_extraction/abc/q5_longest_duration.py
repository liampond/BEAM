"""
Q5: What is the duration of the longest note in this passage?

Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from ..registry import register_extractor


@register_extractor(5, "abc")
def extract(file_path: str) -> str:
    """
    Find the longest note duration in an ABC notation file.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The duration in quarter notes as a string (e.g., "2", "1.5")
    """
    # TODO: Implement ABC parsing for longest note duration
    raise NotImplementedError("ABC Q5 extractor not yet implemented")

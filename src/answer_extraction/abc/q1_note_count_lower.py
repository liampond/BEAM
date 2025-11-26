"""
Q1: How many notes are in the lower staff in this passage?

Include grace notes and ornaments. Count tied notes only once.
Respond with a single number.
"""

from ..registry import register_extractor


@register_extractor(1, "abc")
def extract(file_path: str) -> str:
    """
    Count notes in the lower staff of an ABC notation file.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The count as a string
    """
    # TODO: Implement ABC parsing for lower staff note count
    raise NotImplementedError("ABC Q1 extractor not yet implemented")

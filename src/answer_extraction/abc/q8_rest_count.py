"""
Q8: How many rests are in this passage?

Respond with a number (e.g., 3).
"""

from ..registry import register_extractor


@register_extractor(8, "abc")
def extract(file_path: str) -> str:
    """
    Count rests in an ABC notation file.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The count as a string
    """
    # TODO: Implement ABC parsing for rest count
    raise NotImplementedError("ABC Q8 extractor not yet implemented")

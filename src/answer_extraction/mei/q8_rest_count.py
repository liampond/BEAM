"""
Q8: How many rests are in this passage?

Respond with a number (e.g., 3).
"""

from ..registry import register_extractor


@register_extractor(8, "mei")
def extract(file_path: str) -> str:
    """
    Count rests in an MEI file.
    
    In MEI, rests are <rest> elements.
    
    Args:
        file_path: Path to the MEI (.mei) passage file
    
    Returns:
        The count as a string
    """
    # TODO: Implement MEI parsing for rest count
    raise NotImplementedError("MEI Q8 extractor not yet implemented")

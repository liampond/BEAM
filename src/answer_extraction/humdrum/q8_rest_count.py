"""
Q8: How many rests are in this passage?

Respond with a number (e.g., 3).
"""

from ..registry import register_extractor


@register_extractor(8, "humdrum")
def extract(file_path: str) -> str:
    """
    Count rests in a Humdrum file.
    
    In Humdrum, rests are indicated by 'r' with a duration prefix.
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The count as a string
    """
    # TODO: Implement Humdrum parsing for rest count
    raise NotImplementedError("Humdrum Q8 extractor not yet implemented")

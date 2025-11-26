"""
Q1: How many notes are in the lower staff in this passage?

Include grace notes and ornaments. Count tied notes only once.
Respond with a single number.
"""

from ..registry import register_extractor


@register_extractor(1, "humdrum")
def extract(file_path: str) -> str:
    """
    Count notes in the lower staff (leftmost spine) of a Humdrum file.
    
    In Humdrum, spines are ordered left-to-right with the leftmost
    typically being the lowest voice (bass/left hand).
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The count as a string
    """
    # TODO: Implement Humdrum parsing for lower staff note count
    raise NotImplementedError("Humdrum Q1 extractor not yet implemented")

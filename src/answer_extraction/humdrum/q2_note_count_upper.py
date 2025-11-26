"""
Q2: How many notes are in the upper staff in this passage?

Include grace notes and ornaments. Count tied notes only once.
Respond with a single number.
"""

from ..registry import register_extractor


@register_extractor(2, "humdrum")
def extract(file_path: str) -> str:
    """
    Count notes in the upper staff (rightmost spine) of a Humdrum file.
    
    In Humdrum, spines are ordered left-to-right with the rightmost
    typically being the highest voice (treble/right hand).
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The count as a string
    """
    # TODO: Implement Humdrum parsing for upper staff note count
    raise NotImplementedError("Humdrum Q2 extractor not yet implemented")

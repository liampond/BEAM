"""
Q5: What is the duration of the longest note in this passage?

Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from ..registry import register_extractor


@register_extractor(5, "humdrum")
def extract(file_path: str) -> str:
    """
    Find the longest note duration in a Humdrum file.
    
    Humdrum uses numeric duration encoding where:
    - 1 = whole note (4 quarter notes)
    - 2 = half note (2 quarter notes)
    - 4 = quarter note (1 quarter note)
    - 8 = eighth note (0.5 quarter notes)
    - etc.
    
    Args:
        file_path: Path to the Humdrum (.krn) passage file
    
    Returns:
        The duration in quarter notes as a string (e.g., "2", "1.5")
    """
    # TODO: Implement Humdrum parsing for longest note duration
    raise NotImplementedError("Humdrum Q5 extractor not yet implemented")

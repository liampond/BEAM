"""
Q9: What is the duration of the first note in the lower staff?

If there are multiple simultaneous notes, respond with the duration of the 
highest note. Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from ..registry import register_extractor


@register_extractor(9, "musicxml")
def extract(file_path: str) -> str:
    """
    Find the duration of the first note in lower staff (staff 2).
    
    Args:
        file_path: Path to the MusicXML (.musicxml) passage file
    
    Returns:
        The duration in quarter notes as a string
    """
    # TODO: Implement MusicXML parsing for first lower staff note duration
    raise NotImplementedError("MusicXML Q9 extractor not yet implemented")

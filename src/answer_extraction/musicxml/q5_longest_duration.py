"""
Q5: What is the duration of the longest note in this passage?

Respond in the number of quarter notes (e.g., 2 for a half note).
"""

from ..registry import register_extractor


@register_extractor(5, "musicxml")
def extract(file_path: str) -> str:
    """
    Find the longest note duration in a MusicXML file.
    
    In MusicXML, duration is in <duration> element, relative to <divisions>.
    The formula is: quarter_notes = duration / divisions
    
    Args:
        file_path: Path to the MusicXML (.musicxml) passage file
    
    Returns:
        The duration in quarter notes as a string (e.g., "2", "1.5")
    """
    # TODO: Implement MusicXML parsing for longest note duration
    raise NotImplementedError("MusicXML Q5 extractor not yet implemented")

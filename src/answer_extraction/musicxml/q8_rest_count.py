"""
Q8: How many rests are in this passage?

Respond with a number (e.g., 3).
"""

from ..registry import register_extractor


@register_extractor(8, "musicxml")
def extract(file_path: str) -> str:
    """
    Count rests in a MusicXML file.
    
    In MusicXML, rests are <note> elements with a <rest/> child element.
    
    Args:
        file_path: Path to the MusicXML (.musicxml) passage file
    
    Returns:
        The count as a string
    """
    # TODO: Implement MusicXML parsing for rest count
    raise NotImplementedError("MusicXML Q8 extractor not yet implemented")

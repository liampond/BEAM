"""
Q2: How many notes are in the upper staff in this passage?

Include grace notes and ornaments. Count tied notes only once.
Respond with a single number.
"""

from ..registry import register_extractor


@register_extractor(2, "musicxml")
def extract(file_path: str) -> str:
    """
    Count notes in the upper staff of a MusicXML file.
    
    In MusicXML, staves are indicated by the <staff> element within <note>.
    Staff 1 is typically the upper staff.
    
    Note: MusicXML may have trills written out as multiple notes.
    These should be counted as individual notes per the question.
    
    Args:
        file_path: Path to the MusicXML (.musicxml) passage file
    
    Returns:
        The count as a string
    """
    # TODO: Implement MusicXML parsing for upper staff note count
    raise NotImplementedError("MusicXML Q2 extractor not yet implemented")

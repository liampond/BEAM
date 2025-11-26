"""
Q4: What is the pitch of the lowest note in the lower staff?

Include the octave. Denote octave with scientific pitch notation (e.g., C4).
"""

from ..registry import register_extractor


@register_extractor(4, "musicxml")
def extract(file_path: str) -> str:
    """
    Find the lowest pitch in the lower staff (staff 2).
    
    Args:
        file_path: Path to the MusicXML (.musicxml) passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5")
    """
    # TODO: Implement MusicXML parsing for lowest lower staff pitch
    raise NotImplementedError("MusicXML Q4 extractor not yet implemented")

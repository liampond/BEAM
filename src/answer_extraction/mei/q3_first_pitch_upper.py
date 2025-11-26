"""
Q3: What is the pitch of the first note in the upper staff?

If there are multiple simultaneous notes, respond with the highest pitch.
Denote octave with scientific pitch notation (e.g., C4).
"""

from ..registry import register_extractor


@register_extractor(3, "mei")
def extract(file_path: str) -> str:
    """
    Find the first note pitch in the upper staff (staff 1).
    
    In MEI, pitch is encoded with @pname (pitch class) and @oct (octave).
    Accidentals may be in @accid or @accid.ges.
    
    Args:
        file_path: Path to the MEI (.mei) passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5")
    """
    # TODO: Implement MEI parsing for first upper staff pitch
    raise NotImplementedError("MEI Q3 extractor not yet implemented")

"""
Q3: What is the pitch of the first note in the upper staff?

If there are multiple simultaneous notes, respond with the highest pitch.
Denote octave with scientific pitch notation (e.g., C4).
"""

from ..registry import register_extractor


@register_extractor(3, "musicxml")
def extract(file_path: str) -> str:
    """
    Find the first note pitch in the upper staff (staff 1).
    
    In MusicXML, pitch is encoded with <pitch> containing:
    - <step>: pitch letter (C, D, E, F, G, A, B)
    - <alter>: chromatic alteration (-1, 0, 1, etc.)
    - <octave>: octave number
    
    Args:
        file_path: Path to the MusicXML (.musicxml) passage file
    
    Returns:
        The pitch in scientific notation (e.g., "C4", "F#5")
    """
    # TODO: Implement MusicXML parsing for first upper staff pitch
    raise NotImplementedError("MusicXML Q3 extractor not yet implemented")

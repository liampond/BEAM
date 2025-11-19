"""MusicXML note extractor stub."""

from typing import Dict, List, Tuple, Optional


def extract_musicxml_notes(file_path: str, start_measure: Optional[int] = None, end_measure: Optional[int] = None) -> Dict[int, List[Tuple[int, float, bool]]]:
    """
    Extract notes from MusicXML file as simple (pitch, duration, is_trill) tuples.
    
    Args:
        file_path: Path to .xml/.musicxml file
        start_measure: First measure to extract (None = all)
        end_measure: Last measure to extract (None = all)
    
    Returns:
        Dictionary mapping measure number to list of (pitch, duration, is_trill) tuples
    """
    # TODO: Implement MusicXML extraction
    raise NotImplementedError("MusicXML extractor not yet implemented")

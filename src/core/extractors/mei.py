"""MEI note extractor stub."""

from typing import Dict, List, Tuple, Optional


def extract_mei_notes(file_path: str, start_measure: Optional[int] = None, end_measure: Optional[int] = None) -> Dict[int, List[Tuple[int, float, bool]]]:
    """
    Extract notes from MEI file as simple (pitch, duration, is_trill) tuples.
    
    Args:
        file_path: Path to .mei file
        start_measure: First measure to extract (None = all)
        end_measure: Last measure to extract (None = all)
    
    Returns:
        Dictionary mapping measure number to list of (pitch, duration, is_trill) tuples
    """
    # TODO: Implement MEI extraction
    raise NotImplementedError("MEI extractor not yet implemented")

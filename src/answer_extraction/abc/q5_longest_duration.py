"""
Q5: What is the duration of the longest note in this passage?

Respond in the number of quarter notes (e.g., 2 for a half note, 0.33 for triplet eighth).
Count tied notes as one note - sum their durations.
Excludes grace notes.
Searches both staves.
"""

from ..registry import register_extractor
from .utils import get_longest_duration


@register_extractor(5, "abc")
def extract(file_path: str) -> str:
    """
    Find the longest note duration in an ABC notation file.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The duration in quarter notes as a string (e.g., "2", "1.5", "0.33")
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    longest = get_longest_duration(content)
    
    if longest is None:
        return "0"
    
    # Format: no unnecessary decimals
    if isinstance(longest, int) or longest == int(longest):
        return str(int(longest))
    else:
        return str(longest)

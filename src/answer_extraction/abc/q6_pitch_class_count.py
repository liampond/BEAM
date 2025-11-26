"""
Q6: How many different pitch classes are used in the lower staff?

Consider pitch classes without regard to octave (i.e., all Cs are the same 
pitch class). Respond with a number (e.g., 5).
"""

from ..registry import register_extractor


@register_extractor(6, "abc")
def extract(file_path: str) -> str:
    """
    Count distinct pitch classes in the lower staff of an ABC notation file.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The count as a string
    """
    # TODO: Implement ABC parsing for lower staff pitch class count
    raise NotImplementedError("ABC Q6 extractor not yet implemented")

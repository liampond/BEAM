"""
Extractor Registry

Maps (question_type_id, format) pairs to their corresponding extractor functions.
"""

from typing import Callable, Dict, Tuple, Optional
from pathlib import Path

# Type alias for extractor functions
# Each extractor takes a file path and returns the answer as a string
ExtractorFunc = Callable[[str], str]

# Registry: (question_type_id, format) -> extractor function
_EXTRACTORS: Dict[Tuple[int, str], ExtractorFunc] = {}


def register_extractor(question_type_id: int, format: str):
    """
    Decorator to register an extractor function.
    
    Usage:
        @register_extractor(1, "humdrum")
        def extract(file_path: str) -> str:
            ...
    """
    def decorator(func: ExtractorFunc) -> ExtractorFunc:
        _EXTRACTORS[(question_type_id, format)] = func
        return func
    return decorator


def get_extractor(question_type_id: int, format: str) -> Optional[ExtractorFunc]:
    """
    Get the extractor function for a given question type and format.
    
    Returns None if no extractor is registered.
    """
    return _EXTRACTORS.get((question_type_id, format))


def extract_answer(passage_file: str, question_type_id: int, format: str) -> str:
    """
    Extract the answer to a question from a passage file.
    
    Args:
        passage_file: Path to the passage file
        question_type_id: The question type ID (1-9)
        format: The format ("abc", "humdrum", "mei", "musicxml")
    
    Returns:
        The answer as a string
    
    Raises:
        ValueError: If no extractor is registered for the question/format pair
        FileNotFoundError: If the passage file doesn't exist
    """
    if not Path(passage_file).exists():
        raise FileNotFoundError(f"Passage file not found: {passage_file}")
    
    extractor = get_extractor(question_type_id, format)
    if extractor is None:
        raise ValueError(
            f"No extractor registered for question_type_id={question_type_id}, "
            f"format={format}"
        )
    
    return extractor(passage_file)


def list_registered_extractors() -> list:
    """List all registered (question_type_id, format) pairs."""
    return sorted(_EXTRACTORS.keys())

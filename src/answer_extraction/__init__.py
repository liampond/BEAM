"""
Answer Extraction Module

This module provides format-specific extractors for programmatically generating
ground truth answers to benchmark questions.

Structure:
- abc/       - ABC notation extractors
- humdrum/   - Humdrum/kern extractors  
- mei/       - MEI (Music Encoding Initiative) extractors
- musicxml/  - MusicXML extractors
- utils/     - Shared utility functions (pitch conversion, etc.)

Each format folder contains one extractor per question type (q1, q2, ... q9).
Extractors are format-specific because the encoded representation differs
significantly between formats (e.g., MusicXML writes out trills, staff 
assignments may differ, measure numbering conventions vary).

Usage:
    from src.answer_extraction import extract_answer
    
    answer = extract_answer(
        passage_file="passages/humdrum/P-001.krn",
        question_type_id=1,
        format="humdrum"
    )
"""

from .registry import extract_answer, get_extractor, list_registered_extractors

# Import all format modules to register their extractors
from . import abc
from . import humdrum
from . import mei
from . import musicxml

__all__ = ["extract_answer", "get_extractor", "list_registered_extractors"]

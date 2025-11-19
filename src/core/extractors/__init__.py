"""
Simple note extractors for each format.

Each extractor returns a dictionary mapping measure numbers to lists of notes.
Each note is a simple tuple: (pitch, duration, is_trill)

This avoids complex onset tracking and object models.
"""

from .humdrum import extract_humdrum_notes
from .abc import extract_abc_notes
from .musicxml import extract_musicxml_notes
from .mei import extract_mei_notes

__all__ = [
    'extract_humdrum_notes',
    'extract_abc_notes', 
    'extract_musicxml_notes',
    'extract_mei_notes'
]

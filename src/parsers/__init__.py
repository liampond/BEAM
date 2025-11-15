"""
Music encoding parsers for automated answer generation.

Each format (Humdrum, MusicXML, ABC, MEI) has its own parser that implements
the BaseParser interface for extracting musical information from encoded passages.
"""

from .base_parser import BaseParser
from .humdrum_parser import HumdrumParser

__all__ = ['BaseParser', 'HumdrumParser']

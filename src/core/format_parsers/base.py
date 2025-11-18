"""Abstract base class for format parsers.

This module defines the interface that all format-specific parsers must implement.
The key principle is that parsers extract musical events with temporal information,
allowing comparison based on WHEN notes occur rather than the ORDER they appear
in the file format.

Why This Matters:
----------------
Different formats store multi-voice music in different orders:
- Humdrum: By spine (left-to-right columns)
- ABC: By voice label (V:1, V:2, etc.)
- MusicXML: By part order (arbitrary)
- MEI: By staff order (arbitrary)

The old approach compared pitch sequences directly, which failed when formats
ordered their voices differently. The new approach converts all formats to
time-ordered events, making comparison order-independent.

Example:
--------
Humdrum might extract: [C4, E4, C4, E4] (alternating voices)
MEI might extract:     [C4, C4, E4, E4] (grouped by voice)

Both represent the same music if the onset times are:
Events: [(0.0, C4), (0.0, E4), (1.0, C4), (1.0, E4)]

When sorted by (onset, pitch), both become the same signature.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any

from ..signature import MusicalSignature


class FormatParser(ABC):
    """Abstract base class for music format parsers.
    
    Each format-specific parser (Humdrum, ABC, MusicXML, MEI) extends this class
    and implements the extract_signature() method.
    
    Attributes:
        name: Human-readable name of the format (e.g., "Humdrum", "ABC")
        file_extensions: Tuple of valid file extensions (e.g., ('.krn',))
    """
    
    def __init__(self):
        """Initialize the parser."""
        self._validate_class_attributes()
    
    def _validate_class_attributes(self):
        """Ensure subclasses define required class attributes."""
        if not hasattr(self.__class__, 'name'):
            raise NotImplementedError(
                f"{self.__class__.__name__} must define a 'name' class attribute"
            )
        if not hasattr(self.__class__, 'file_extensions'):
            raise NotImplementedError(
                f"{self.__class__.__name__} must define a 'file_extensions' class attribute"
            )
    
    @abstractmethod
    def extract_signature(
        self,
        file_path: Path,
        start_measure: int,
        end_measure: int,
        **kwargs
    ) -> Optional[MusicalSignature]:
        """Extract a musical signature from a file.
        
        This is the core method that all format parsers must implement. It reads
        the specified measure range from the file and returns a MusicalSignature
        containing time-ordered musical events.
        
        CRITICAL REQUIREMENT: Events Must Be Time-Ordered
        --------------------------------------------------
        The returned MusicalSignature must contain events with accurate onset times.
        Events will be automatically sorted by (onset, pitch) in the MusicalSignature
        constructor, but onset times must be calculated correctly relative to the
        start of the passage.
        
        Time Calculation Guidelines:
        - onset=0.0 represents the start of the first measure
        - For 4/4 time, measure 1 spans [0.0, 4.0), measure 2 spans [4.0, 8.0), etc.
        - For 3/4 time, measure 1 spans [0.0, 3.0), measure 2 spans [3.0, 6.0), etc.
        - Grace notes should have is_grace=True and onset equal to their parent note
        - Simultaneous notes (chords) have the same onset time
        
        Args:
            file_path: Path to the music file to parse
            start_measure: First measure number to extract (1-indexed)
            end_measure: Last measure number to extract (inclusive, 1-indexed)
            **kwargs: Format-specific options (e.g., voice selection, interpretation)
        
        Returns:
            MusicalSignature with time-ordered events, or None if extraction fails
        
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If measure range is invalid
            ParseError: If the file format is malformed
        
        Example:
            >>> parser = HumdrumParser()
            >>> sig = parser.extract_signature(
            ...     Path("data/humdrum/01-1.krn"),
            ...     start_measure=1,
            ...     end_measure=3
            ... )
            >>> print(sig.note_count)
            24
            >>> print(sig.events[:3])  # First three events, sorted by (onset, pitch)
            [Event(onset=0.0, pitch=60, duration=1.0),
             Event(onset=0.0, pitch=64, duration=1.0),
             Event(onset=1.0, pitch=62, duration=0.5)]
        """
        pass
    
    def supports_file(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file.
        
        Args:
            file_path: Path to check
        
        Returns:
            True if the file extension matches this parser's format
        
        Example:
            >>> parser = HumdrumParser()
            >>> parser.supports_file(Path("score.krn"))
            True
            >>> parser.supports_file(Path("score.abc"))
            False
        """
        return file_path.suffix.lower() in self.file_extensions
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get parser metadata.
        
        Returns:
            Dictionary with parser name, supported extensions, and other info
        
        Example:
            >>> parser = HumdrumParser()
            >>> parser.get_metadata()
            {'name': 'Humdrum', 'extensions': ['.krn'], 'version': '1.0'}
        """
        return {
            'name': self.name,
            'extensions': list(self.file_extensions),
            'class': self.__class__.__name__,
        }
    
    def __repr__(self) -> str:
        """String representation of the parser."""
        return f"{self.__class__.__name__}(name='{self.name}')"

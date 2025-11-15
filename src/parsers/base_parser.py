"""
Base parser abstract class defining the interface for all format-specific parsers.

All parsers must implement these methods to support automated answer generation
for the benchmark question types.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class Note:
    """Represents a single note in a musical passage."""
    pitch: str  # Scientific pitch notation (e.g., "C4", "F#5", "Bb3")
    octave: int
    duration: float  # Duration in quarter note units (e.g., 1.0 = quarter, 0.5 = eighth)
    duration_text: str  # Human-readable (e.g., "Quarter note", "Dotted eighth note")
    hand: str  # "left" or "right"
    position: float  # Beat position within measure (0-indexed)
    is_grace: bool = False
    is_rest: bool = False
    is_tied_continuation: bool = False  # True if this is the continuation of a tied note


class BaseParser(ABC):
    """
    Abstract base class for music encoding parsers.
    
    Each format-specific parser (Humdrum, MusicXML, ABC, MEI) must implement
    all abstract methods to support the full range of question types.
    """
    
    @abstractmethod
    def parse_passage(self, passage_text: str) -> Tuple[List[Note], List[Note]]:
        """
        Parse a passage and return separate note lists for left and right hands.
        
        Args:
            passage_text: The encoded musical passage
            
        Returns:
            Tuple of (left_hand_notes, right_hand_notes)
        """
        pass
    
    @abstractmethod
    def count_notes(
        self, 
        passage_text: str, 
        hand: Optional[str] = None,
        include_grace: bool = True,
        count_tied_once: bool = True
    ) -> int:
        """
        Count notes in a passage.
        
        Args:
            passage_text: The encoded musical passage
            hand: "left", "right", or None for both hands
            include_grace: Whether to include grace notes
            count_tied_once: Count tied notes only once (not their continuations)
            
        Returns:
            Number of notes
        """
        pass
    
    @abstractmethod
    def count_rests(self, passage_text: str) -> int:
        """
        Count rests in a passage.
        
        Args:
            passage_text: The encoded musical passage
            
        Returns:
            Number of rests
        """
        pass
    
    @abstractmethod
    def count_pitch_classes(
        self, 
        passage_text: str, 
        hand: str
    ) -> int:
        """
        Count unique pitch classes in a hand (atonal sense: Bb and B are distinct).
        
        Args:
            passage_text: The encoded musical passage
            hand: "left" or "right"
            
        Returns:
            Number of unique pitch classes
        """
        pass
    
    @abstractmethod
    def get_first_pitch(
        self, 
        passage_text: str, 
        hand: str,
        include_octave: bool = True
    ) -> str:
        """
        Get the pitch of the first note in the specified hand.
        If multiple simultaneous notes, choose the highest.
        
        Args:
            passage_text: The encoded musical passage
            hand: "left" or "right"
            include_octave: Whether to include octave designation
            
        Returns:
            Pitch string (e.g., "C4", "F#5")
        """
        pass
    
    @abstractmethod
    def get_lowest_pitch(
        self, 
        passage_text: str, 
        hand: str,
        include_octave: bool = True
    ) -> str:
        """
        Get the lowest pitch in the specified hand.
        
        Args:
            passage_text: The encoded musical passage
            hand: "left" or "right"
            include_octave: Whether to include octave designation
            
        Returns:
            Pitch string (e.g., "C3")
        """
        pass
    
    @abstractmethod
    def get_highest_pitch(
        self, 
        passage_text: str, 
        hand: str,
        include_octave: bool = True
    ) -> str:
        """
        Get the highest pitch in the specified hand.
        
        Args:
            passage_text: The encoded musical passage
            hand: "left" or "right"
            include_octave: Whether to include octave designation
            
        Returns:
            Pitch string (e.g., "G5")
        """
        pass
    
    @abstractmethod
    def get_first_note_duration(
        self, 
        passage_text: str, 
        hand: str,
        as_text: bool = True
    ) -> str:
        """
        Get the duration of the first note in the specified hand.
        If multiple simultaneous notes, choose the highest.
        
        Args:
            passage_text: The encoded musical passage
            hand: "left" or "right"
            as_text: Return human-readable text (True) or beats (False)
            
        Returns:
            Duration string (e.g., "Dotted eighth note" or "0.75")
        """
        pass
    
    @abstractmethod
    def get_longest_note_duration(
        self, 
        passage_text: str,
        as_text: bool = False
    ) -> str:
        """
        Get the duration of the longest note in the passage.
        
        Args:
            passage_text: The encoded musical passage
            as_text: Return human-readable text (True) or beats (False)
            
        Returns:
            Duration string (e.g., "4" for whole note, "Half note")
        """
        pass
    
    @abstractmethod
    def calculate_interval(
        self, 
        passage_text: str, 
        hand: str
    ) -> int:
        """
        Calculate the interval in semitones between the first and last notes.
        
        Args:
            passage_text: The encoded musical passage
            hand: "left" or "right"
            
        Returns:
            Interval in semitones (e.g., 7 for a perfect fifth)
        """
        pass
    
    @abstractmethod
    def get_beat_position(
        self, 
        passage_text: str, 
        pitch: str, 
        hand: str
    ) -> Optional[float]:
        """
        Find on which beat a specific pitch first appears.
        
        Args:
            passage_text: The encoded musical passage
            pitch: The pitch to search for (e.g., "E5")
            hand: "left" or "right"
            
        Returns:
            Beat number (1-indexed) or None if not found
        """
        pass
    
    @abstractmethod
    def count_note_type(
        self, 
        passage_text: str, 
        note_type: str,
        hand: Optional[str] = None
    ) -> int:
        """
        Count specific note types (e.g., half notes, sixteenth notes).
        
        Args:
            passage_text: The encoded musical passage
            note_type: Type of note to count (e.g., "half", "sixteenth")
            hand: "left", "right", or None for both hands
            
        Returns:
            Number of notes of that type
        """
        pass
    
    # Helper methods (optional to override)
    
    def pitch_to_semitones(self, pitch: str) -> int:
        """
        Convert pitch to MIDI note number for interval calculations.
        
        Args:
            pitch: Pitch string (e.g., "C4", "F#5", "Bb3")
            
        Returns:
            MIDI note number (C4 = 60)
        """
        # Parse pitch string
        import re
        match = re.match(r'([A-G][b#]?)(\d+)', pitch)
        if not match:
            raise ValueError(f"Invalid pitch format: {pitch}")
        
        note_name = match.group(1)
        octave = int(match.group(2))
        
        # Pitch class to semitone offset
        pitch_class_map = {
            'C': 0, 'C#': 1, 'Db': 1,
            'D': 2, 'D#': 3, 'Eb': 3,
            'E': 4,
            'F': 5, 'F#': 6, 'Gb': 6,
            'G': 7, 'G#': 8, 'Ab': 8,
            'A': 9, 'A#': 10, 'Bb': 10,
            'B': 11
        }
        
        semitone = pitch_class_map[note_name] + (octave + 1) * 12
        return semitone
    
    def duration_to_text(self, duration: float) -> str:
        """
        Convert numeric duration to human-readable text.
        
        Args:
            duration: Duration in quarter notes (e.g., 1.0, 0.5, 1.5)
            
        Returns:
            Human-readable duration (e.g., "Quarter note", "Dotted half note")
        """
        duration_map = {
            4.0: "Whole note",
            3.0: "Dotted half note",
            2.0: "Half note",
            1.5: "Dotted quarter note",
            1.0: "Quarter note",
            0.75: "Dotted eighth note",
            0.5: "Eighth note",
            0.375: "Dotted sixteenth note",
            0.25: "Sixteenth note",
            0.125: "Thirty-second note",
        }
        
        return duration_map.get(duration, f"{duration} beats")

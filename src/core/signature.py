"""
Musical signature data structures.

Represents musical content in a format-agnostic way for comparison
across different encoding formats (Humdrum, ABC, MusicXML, MEI).
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class NoteType(Enum):
    """Type of musical event."""
    NOTE = "note"
    CHORD = "chord"
    REST = "rest"
    GRACE = "grace"


@dataclass
class Event:
    """
    A single musical event (note or chord) with temporal information.
    
    The key insight: events are compared by (onset_time, pitch), not by
    the order they appear in the encoding format.
    """
    onset: float  # Time in quarter notes from start of passage
    pitch: int    # MIDI pitch number (60 = middle C)
    duration: float  # Duration in quarter notes
    
    # Optional metadata
    voice: Optional[int] = None  # Voice/staff number (for debugging)
    is_grace: bool = False
    
    def __lt__(self, other: 'Event') -> bool:
        """Sort by onset time, then pitch."""
        if self.onset != other.onset:
            return self.onset < other.onset
        return self.pitch < other.pitch
    
    def __eq__(self, other: object) -> bool:
        """Two events are equal if they have same onset, pitch, and duration."""
        if not isinstance(other, Event):
            return NotImplemented
        return (
            abs(self.onset - other.onset) < 0.01 and  # Small tolerance for float comparison
            self.pitch == other.pitch and
            abs(self.duration - other.duration) < 0.01
        )
    
    def __hash__(self) -> int:
        """Hash based on onset and pitch (for set operations)."""
        # Round to avoid float precision issues
        return hash((round(self.onset, 2), self.pitch, round(self.duration, 2)))


@dataclass
class MusicalSignature:
    """
    A format-agnostic representation of musical content.
    
    This is what we extract from each format and compare.
    The events list is ALWAYS sorted by (onset, pitch) to ensure
    order-independent comparison.
    """
    events: List[Event] = field(default_factory=list)
    measure_count: int = 1
    total_duration: float = 0.0
    
    # Metadata for debugging
    source_format: Optional[str] = None  # 'humdrum', 'abc', 'musicxml', 'mei'
    start_measure: Optional[int] = None
    end_measure: Optional[int] = None
    
    def __post_init__(self):
        """Ensure events are always sorted."""
        self.events.sort()
    
    @property
    def note_count(self) -> int:
        """Total number of events (excluding grace notes)."""
        return sum(1 for e in self.events if not e.is_grace)
    
    @property
    def pitches(self) -> List[int]:
        """List of pitches in temporal order (for backwards compatibility)."""
        return [e.pitch for e in self.events if not e.is_grace]
    
    @property
    def pitch_set(self) -> set:
        """Set of unique pitches (for quick comparison)."""
        return {e.pitch for e in self.events if not e.is_grace}
    
    @property
    def first_events(self, n: int = 5) -> List[Event]:
        """First N events (for multi-measure boundary checking)."""
        non_grace = [e for e in self.events if not e.is_grace]
        return non_grace[:n]
    
    @property
    def last_events(self, n: int = 5) -> List[Event]:
        """Last N events (for multi-measure boundary checking)."""
        non_grace = [e for e in self.events if not e.is_grace]
        return non_grace[-n:]
    
    def time_slice(self, start: float, end: float) -> List[Event]:
        """Get all events within a time range."""
        return [e for e in self.events if start <= e.onset < end]
    
    def has_rapid_notes(self, threshold: float = 0.25) -> bool:
        """Check if >30% of notes are shorter than threshold (quarter note)."""
        if not self.events:
            return False
        rapid_count = sum(1 for e in self.events if not e.is_grace and e.duration <= threshold)
        return (rapid_count / self.note_count) > 0.3 if self.note_count > 0 else False
    
    def chord_count(self) -> int:
        """Count simultaneous note groups (chords)."""
        if not self.events:
            return 0
        
        # Group events by onset time
        onset_times = {}
        for event in self.events:
            if not event.is_grace:
                onset = round(event.onset, 2)  # Round to avoid float precision issues
                if onset not in onset_times:
                    onset_times[onset] = 0
                onset_times[onset] += 1
        
        # Count onsets with 2+ simultaneous notes
        return sum(1 for count in onset_times.values() if count >= 2)
    
    def __repr__(self) -> str:
        """Human-readable representation."""
        return (
            f"MusicalSignature("
            f"events={len(self.events)}, "
            f"measures={self.measure_count}, "
            f"duration={self.total_duration}, "
            f"format={self.source_format})"
        )


def create_signature_from_legacy(
    pitches: List[int],
    durations: List[float],
    measure_count: int = 1,
    source_format: Optional[str] = None
) -> MusicalSignature:
    """
    Create a MusicalSignature from legacy pitch/duration lists.
    
    This is for backwards compatibility with existing extraction code.
    We assume durations are sequential (no overlap), so we calculate
    onset times by cumulative duration.
    
    Args:
        pitches: List of MIDI pitch numbers
        durations: List of durations (in quarter notes)
        measure_count: Number of measures
        source_format: Format name for debugging
        
    Returns:
        MusicalSignature with events in temporal order
    """
    events = []
    current_onset = 0.0
    
    for pitch, duration in zip(pitches, durations):
        event = Event(
            onset=current_onset,
            pitch=pitch,
            duration=duration
        )
        events.append(event)
        current_onset += duration
    
    return MusicalSignature(
        events=events,
        measure_count=measure_count,
        total_duration=current_onset,
        source_format=source_format
    )

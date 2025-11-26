"""
Shared utility functions for answer extraction.

These utilities are format-agnostic and handle common operations like:
- Pitch string parsing and conversion
- MIDI number calculations
- Pitch class extraction
- Duration normalization
"""

from .pitch import (
    pitch_to_midi,
    midi_to_pitch,
    pitch_to_class,
    interval_in_semitones,
)

__all__ = [
    "pitch_to_midi",
    "midi_to_pitch", 
    "pitch_to_class",
    "interval_in_semitones",
]

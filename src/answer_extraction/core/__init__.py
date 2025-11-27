"""
Core utilities for answer extraction - format-agnostic.

These utilities work with standardized representations (scientific pitch notation,
quarter note durations) rather than format-specific syntax.
"""

from .pitch import pitch_to_midi, midi_to_pitch_class, calculate_interval_semitones
from .duration import format_duration

__all__ = [
    # Pitch utilities
    'pitch_to_midi',
    'midi_to_pitch_class', 
    'calculate_interval_semitones',
    # Duration utilities
    'format_duration',
]

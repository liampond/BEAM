"""
Format-agnostic pitch utilities.

These work with scientific pitch notation (e.g., "C4", "F#5", "Bb3") 
and MIDI note numbers.
"""

import re
from typing import Optional


# Base pitch class values (C = 0, semitones from C)
PITCH_CLASS_MAP = {
    'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
}

# Reverse map for MIDI to pitch name
PITCH_CLASS_TO_NAME = {
    0: 'C', 1: 'C#', 2: 'D', 3: 'Eb', 4: 'E', 5: 'F',
    6: 'F#', 7: 'G', 8: 'Ab', 9: 'A', 10: 'Bb', 11: 'B'
}


def pitch_to_midi(scientific_pitch: str) -> int:
    """
    Convert scientific pitch notation to MIDI note number.
    
    Args:
        scientific_pitch: Pitch in scientific notation, e.g., "C4", "F#5", "Bb3"
    
    Returns:
        MIDI note number (C4 = 60)
    
    Examples:
        >>> pitch_to_midi("C4")
        60
        >>> pitch_to_midi("A4")
        69
        >>> pitch_to_midi("F#5")
        78
        >>> pitch_to_midi("Bb3")
        58
    """
    match = re.match(r'([A-G])(#|##|b|bb)?(\d+)', scientific_pitch)
    if not match:
        return 0
    
    note_letter = match.group(1)
    accidental = match.group(2) or ''
    octave = int(match.group(3))
    
    # Base pitch class
    pitch_class = PITCH_CLASS_MAP[note_letter]
    
    # Apply accidental
    if accidental == '#':
        pitch_class += 1
    elif accidental == '##':
        pitch_class += 2
    elif accidental == 'b':
        pitch_class -= 1
    elif accidental == 'bb':
        pitch_class -= 2
    
    # MIDI number: C4 = 60, so C-1 = 0
    # Formula: (octave + 1) * 12 + pitch_class
    return (octave + 1) * 12 + pitch_class


def midi_to_pitch_class(midi_num: int) -> int:
    """
    Convert MIDI note number to pitch class (0-11).
    
    Pitch classes are octave-independent, so C in any octave = 0.
    Enharmonic equivalents map to the same pitch class (Eb = D# = 3).
    
    Args:
        midi_num: MIDI note number
    
    Returns:
        Pitch class (0-11, where C=0, C#/Db=1, D=2, etc.)
    
    Examples:
        >>> midi_to_pitch_class(60)  # C4
        0
        >>> midi_to_pitch_class(72)  # C5
        0
        >>> midi_to_pitch_class(63)  # Eb4 or D#4
        3
    """
    return midi_num % 12


def calculate_interval_semitones(pitch1: str, pitch2: str) -> int:
    """
    Calculate the interval between two pitches in semitones.
    
    Returns the absolute value (always positive).
    
    Args:
        pitch1: First pitch in scientific notation
        pitch2: Second pitch in scientific notation
    
    Returns:
        Number of semitones between the pitches (absolute value)
    
    Examples:
        >>> calculate_interval_semitones("C4", "G4")  # Perfect fifth
        7
        >>> calculate_interval_semitones("C4", "C5")  # Octave
        12
        >>> calculate_interval_semitones("E4", "C4")  # Major third down
        4
    """
    midi1 = pitch_to_midi(pitch1)
    midi2 = pitch_to_midi(pitch2)
    return abs(midi2 - midi1)


def midi_to_scientific(midi_num: int, prefer_sharps: bool = True) -> str:
    """
    Convert MIDI note number to scientific pitch notation.
    
    Args:
        midi_num: MIDI note number
        prefer_sharps: If True, use sharps for black keys; if False, use flats
    
    Returns:
        Scientific pitch notation (e.g., "C4", "F#5")
    
    Examples:
        >>> midi_to_scientific(60)
        'C4'
        >>> midi_to_scientific(61, prefer_sharps=True)
        'C#4'
        >>> midi_to_scientific(61, prefer_sharps=False)
        'Db4'
    """
    pitch_class = midi_num % 12
    octave = (midi_num // 12) - 1
    
    if prefer_sharps:
        names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    else:
        names = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
    
    return f"{names[pitch_class]}{octave}"

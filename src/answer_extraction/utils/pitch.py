"""
Pitch utility functions.

Handles conversion between different pitch representations:
- Scientific pitch notation (e.g., "C4", "F#5", "Bb3")
- MIDI note numbers (e.g., 60 for C4)
- Pitch classes (e.g., "C", "F#", "Bb")
"""

import re
from typing import Optional

# Mapping from pitch class to semitones above C
_PITCH_CLASS_TO_SEMITONES = {
    'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
}

# Accidental adjustments
_ACCIDENTAL_ADJUSTMENT = {
    '#': 1, '##': 2, 'x': 2,  # sharps
    'b': -1, 'bb': -2,        # flats
    'n': 0, '': 0             # natural or none
}


def pitch_to_midi(pitch: str) -> int:
    """
    Convert scientific pitch notation to MIDI note number.
    
    Args:
        pitch: Scientific pitch notation (e.g., "C4", "F#5", "Bb3", "C##4")
    
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
    # Parse the pitch string: letter + optional accidentals + octave
    match = re.match(r'^([A-Ga-g])(#{1,2}|x|b{1,2}|n)?(-?\d+)$', pitch)
    if not match:
        raise ValueError(f"Invalid pitch notation: {pitch}")
    
    letter, accidental, octave = match.groups()
    letter = letter.upper()
    accidental = accidental or ''
    octave = int(octave)
    
    # Calculate MIDI note number
    # C4 = 60, so C0 = 12
    base_midi = (octave + 1) * 12
    semitones = _PITCH_CLASS_TO_SEMITONES[letter]
    adjustment = _ACCIDENTAL_ADJUSTMENT.get(accidental, 0)
    
    return base_midi + semitones + adjustment


def midi_to_pitch(midi: int, prefer_sharps: bool = True) -> str:
    """
    Convert MIDI note number to scientific pitch notation.
    
    Args:
        midi: MIDI note number (C4 = 60)
        prefer_sharps: If True, use sharps; if False, use flats
    
    Returns:
        Scientific pitch notation
    
    Examples:
        >>> midi_to_pitch(60)
        'C4'
        >>> midi_to_pitch(61, prefer_sharps=True)
        'C#4'
        >>> midi_to_pitch(61, prefer_sharps=False)
        'Db4'
    """
    octave = (midi // 12) - 1
    semitone = midi % 12
    
    if prefer_sharps:
        names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    else:
        names = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
    
    return f"{names[semitone]}{octave}"


def pitch_to_class(pitch: str) -> str:
    """
    Extract the pitch class from scientific pitch notation.
    
    The pitch class is the note name with accidentals, without the octave.
    
    Args:
        pitch: Scientific pitch notation (e.g., "C4", "F#5", "Bb3")
    
    Returns:
        Pitch class (e.g., "C", "F#", "Bb")
    
    Examples:
        >>> pitch_to_class("C4")
        'C'
        >>> pitch_to_class("F#5")
        'F#'
        >>> pitch_to_class("Bb3")
        'Bb'
    """
    match = re.match(r'^([A-Ga-g])(#{1,2}|x|b{1,2}|n)?(-?\d+)$', pitch)
    if not match:
        raise ValueError(f"Invalid pitch notation: {pitch}")
    
    letter, accidental, _ = match.groups()
    letter = letter.upper()
    accidental = accidental or ''
    
    # Normalize: 'n' (natural) becomes empty, 'x' becomes '##'
    if accidental == 'n':
        accidental = ''
    elif accidental == 'x':
        accidental = '##'
    
    return f"{letter}{accidental}"


def interval_in_semitones(pitch1: str, pitch2: str) -> int:
    """
    Calculate the interval between two pitches in semitones.
    
    Returns the absolute value (always positive).
    
    Args:
        pitch1: First pitch in scientific notation
        pitch2: Second pitch in scientific notation
    
    Returns:
        Absolute interval in semitones
    
    Examples:
        >>> interval_in_semitones("C4", "G4")
        7
        >>> interval_in_semitones("C4", "C5")
        12
        >>> interval_in_semitones("E4", "C4")
        4
    """
    midi1 = pitch_to_midi(pitch1)
    midi2 = pitch_to_midi(pitch2)
    return abs(midi2 - midi1)

"""
Simple Humdrum note extractor.

Returns: Dict[measure_number, List[(pitch, duration, is_trill)]]

No onset tracking, no voice tracking - just extract notes by measure.
"""

import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path


def extract_humdrum_notes(file_path: str, start_measure: Optional[int] = None, end_measure: Optional[int] = None) -> Dict[int, List[Tuple[int, float, bool]]]:
    """
    Extract notes from Humdrum file as simple (pitch, duration, is_trill) tuples.
    
    Args:
        file_path: Path to .krn file
        start_measure: First measure to extract (None = all)
        end_measure: Last measure to extract (None = all)
    
    Returns:
        Dictionary mapping measure number to list of (pitch, duration, is_trill) tuples
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f]
    
    measures = {}
    current_measure = None
    current_notes = []
    kern_spines = []
    
    for line in lines:
        # Skip comments and empty lines
        if line.startswith('!') or not line.strip():
            continue
        
        # Detect kern spines
        if line.startswith('**'):
            tokens = line.split('\t')
            kern_spines = [i for i, token in enumerate(tokens) if token == '**kern']
            continue
        
        # Skip interpretations
        if line.startswith('*'):
            continue
        
        # Handle measure markers
        if line.startswith('='):
            # Save previous measure
            if current_measure is not None:
                if start_measure is None or start_measure <= current_measure <= (end_measure or current_measure):
                    measures[current_measure] = current_notes
            
            # Start new measure
            tokens = line.split('\t')
            measure_match = re.search(r'=(\d+)', tokens[0])
            if measure_match:
                current_measure = int(measure_match.group(1))
                current_notes = []
            continue
        
        # Parse data lines
        if current_measure is not None and '\t' in line:
            tokens = line.split('\t')
            
            for spine_idx in kern_spines:
                if spine_idx >= len(tokens):
                    continue
                
                token = tokens[spine_idx]
                
                # Skip null tokens (sustained notes) and rests
                if not token or token == '.' or token == 'r' or re.match(r'^\d+\.?r', token):
                    continue
                
                # Extract notes from this token
                notes = _parse_humdrum_token(token)
                current_notes.extend(notes)
    
    # Save final measure
    if current_measure is not None:
        if start_measure is None or start_measure <= current_measure <= (end_measure or current_measure):
            measures[current_measure] = current_notes
    
    return measures


def _parse_humdrum_token(token: str) -> List[Tuple[int, float, bool]]:
    """
    Parse a single Humdrum token into (pitch, duration, is_trill) tuples.
    
    Args:
        token: Humdrum token (e.g., '8ffTL', '4c 4e 4g', 'r')
    
    Returns:
        List of (pitch, duration, is_trill) tuples
    """
    notes = []
    
    # Get duration
    duration = _get_duration(token)
    if duration == 0:
        return notes
    
    # Check for trill
    has_trill = 'T' in token or 't' in token
    
    # Extract pitches (handles chords)
    pitches = _extract_pitches(token)
    
    for pitch in pitches:
        if pitch is not None:
            notes.append((pitch, duration, has_trill))
    
    return notes


def _get_duration(token: str) -> float:
    """Extract duration in quarter notes from Humdrum token."""
    if not token or token == '.':
        return 0.0
    
    # Handle chords - take duration from first note
    if ' ' in token:
        token = token.split()[0]
    
    # Skip leading non-numeric characters (like parentheses)
    duration_str = ''
    for char in token:
        if char.isdigit():
            duration_str += char
        elif duration_str:
            # Stop after we've found digits
            break
    
    if not duration_str:
        return 0.0
    
    try:
        rhythmic_value = int(duration_str)
    except ValueError:
        return 0.0
    
    # Convert to quarter notes: 1=whole, 2=half, 4=quarter, 8=eighth, etc.
    base_duration = 4.0 / rhythmic_value
    
    # Handle dotted notes
    dot_count = token.count('.')
    if dot_count == 0:
        return base_duration
    elif dot_count == 1:
        return base_duration * 1.5
    elif dot_count == 2:
        return base_duration * 1.75
    else:
        return base_duration * (2 - (0.5 ** dot_count))


def _extract_pitches(token: str) -> List[int]:
    """Extract MIDI pitch(es) from Humdrum token."""
    # Handle rests
    if 'r' in token.lower() and not any(c.isalpha() and c not in 'rqTLJ#-n' for c in token):
        return []
    
    # Split chords (space-separated)
    if ' ' in token:
        chord_tokens = token.split(' ')
        pitches = []
        for ct in chord_tokens:
            pitches.extend(_extract_pitches(ct))
        return pitches
    
    # Remove rhythm digits and ornaments
    pitch_part = re.sub(r'^\(?\d+\.?', '', token)  # Remove leading rhythm (with optional paren)
    pitch_part = re.sub(r'[TtLJqQ\[\]()]', '', pitch_part)  # Remove ornaments and parens
    
    if not pitch_part or pitch_part == 'r':
        return []
    
    # Extract pitch letters
    pitch_letters = []
    for char in pitch_part:
        if char.isalpha() and char not in ['n', 's', 'S']:
            pitch_letters.append(char)
    
    if not pitch_letters:
        return []
    
    # First letter determines pitch class
    first_letter = pitch_letters[0].lower()
    pitch_map = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
    
    if first_letter not in pitch_map:
        return []
    
    base_pitch = pitch_map[first_letter]
    
    # Determine octave
    if pitch_letters[0].islower():
        # Lowercase: start at octave 4, go up with repetitions
        octave = 4 + (len(pitch_letters) - 1)
    else:
        # Uppercase: start at octave 3, go down with repetitions
        octave = 3 - (len(pitch_letters) - 1)
    
    # Handle accidentals
    accidental = 0
    if '#' in pitch_part:
        accidental = 1
    elif '-' in pitch_part:
        accidental = -1
    
    # Calculate MIDI pitch
    midi_pitch = (octave + 1) * 12 + base_pitch + accidental
    
    return [midi_pitch]

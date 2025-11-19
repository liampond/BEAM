"""
Simple ABC note extractor.

Returns: Dict[measure_number, List[(pitch, duration, is_trill)]]
"""

import re
from typing import Dict, List, Tuple, Optional


def extract_abc_notes(file_path: str, start_measure: Optional[int] = None, end_measure: Optional[int] = None) -> Dict[int, List[Tuple[int, float, bool]]]:
    """
    Extract notes from ABC file as simple (pitch, duration, is_trill) tuples.
    
    Args:
        file_path: Path to .abc file
        start_measure: First measure to extract (None = all)
        end_measure: Last measure to extract (None = all)
    
    Returns:
        Dictionary mapping measure number to list of (pitch, duration, is_trill) tuples
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f]
    
    # Parse header to get unit note length
    unit_length = 1/16  # Default for this file (L: 1/16)
    
    for line in lines:
        if line.startswith('L:'):
            # Parse like "L: 1/16"
            match = re.search(r'L:\s*(\d+)/(\d+)', line)
            if match:
                unit_length = int(match.group(1)) / int(match.group(2))
    
    # Convert unit length to quarter notes
    # 1/16 note = 0.25 quarter notes
    unit_in_qn = unit_length * 4.0
    
    # Parse voices - collect all music lines
    voice_lines = {'1': [], '2': []}
    current_voice = None
    
    for line in lines:
        # Skip header lines
        if line.startswith(('%', 'X:', 'T:', 'C:', 'M:', 'Q:', 'K:', 'L:', 'N:', 'V:')):
            if line.startswith('V:'):
                # Extract voice number
                match = re.search(r'V:\s*(\d+)', line)
                if match:
                    current_voice = match.group(1)
            continue
        
        # Skip empty lines
        if not line.strip():
            continue
        
        # Check for voice indicator at start of line
        if line.startswith('[V:'):
            match = re.match(r'\[V:(\d+)\]\s*(.*)$', line)
            if match:
                current_voice = match.group(1)
                music_content = match.group(2)
                if music_content.strip():
                    voice_lines[current_voice].append(music_content)
            continue
        
        # Regular music line
        if current_voice and line.strip():
            voice_lines[current_voice].append(line)
    
    # Now parse measures from each voice
    # In ABC, measures are delimited by |
    # We need to parse both voices and merge notes by measure number
    all_voice_measures = {}
    
    for voice_num, lines_list in voice_lines.items():
        # Join all lines for this voice
        full_music = ' '.join(lines_list)
        
        # Split by measure markers
        # Handle various bar types: |, ||, |:, :|, :|]|:, etc.
        measure_texts = re.split(r'\|+:?\]?:?', full_music)
        
        # Parse each measure
        for measure_idx, measure_text in enumerate(measure_texts, start=1):
            if not measure_text.strip():
                continue
            
            # Parse notes in this measure
            notes = _parse_abc_measure(measure_text, unit_in_qn)
            
            # Store by voice and measure
            if measure_idx not in all_voice_measures:
                all_voice_measures[measure_idx] = []
            all_voice_measures[measure_idx].extend(notes)
    
    # Filter by requested range and return
    measures = {}
    for measure_num, note_list in all_voice_measures.items():
        if start_measure and measure_num < start_measure:
            continue
        if end_measure and measure_num > end_measure:
            continue
        measures[measure_num] = note_list
    
    return measures


def _parse_abc_measure(measure_text: str, unit_in_qn: float) -> List[Tuple[int, float, bool]]:
    """Parse notes from an ABC measure."""
    notes = []
    
    # Remove decorations/annotations that aren't trills
    # Keep !trill! markers
    has_trill = '!trill!' in measure_text.lower()
    
    # Tokenize the measure
    # ABC tokens can be: notes, chords [CEG], rests z, decorations !...!
    tokens = _tokenize_abc(measure_text)
    
    for token in tokens:
        parsed = _parse_abc_token(token, unit_in_qn, has_trill)
        notes.extend(parsed)
    
    return notes


def _tokenize_abc(text: str) -> List[str]:
    """
    Tokenize ABC music text.
    
    Returns list of tokens (notes, chords, rests, etc.)
    """
    tokens = []
    i = 0
    
    while i < len(text):
        # Skip whitespace
        if text[i].isspace():
            i += 1
            continue
        
        # Chord: [...]
        if text[i] == '[' and i + 1 < len(text) and text[i+1] != 'V':
            # Find matching ]
            j = i + 1
            while j < len(text) and text[j] != ']':
                j += 1
            if j < len(text):
                tokens.append(text[i:j+1])
                i = j + 1
                continue
        
        # Decoration: !...!
        if text[i] == '!':
            j = i + 1
            while j < len(text) and text[j] != '!':
                j += 1
            if j < len(text):
                # Skip decorations (we handle trills separately)
                i = j + 1
                continue
        
        # Grace notes: {...}
        if text[i] == '{':
            j = i + 1
            while j < len(text) and text[j] != '}':
                j += 1
            if j < len(text):
                # Skip grace notes for now
                i = j + 1
                continue
        
        # Single note or rest
        if text[i] in 'abcdefgABCDEFGz^=_':
            # Collect note: [accidental]pitch[octave_mods][duration]
            j = i
            
            # Optional accidental
            if text[j] in '^=_':
                j += 1
            
            # Pitch letter (required)
            if j < len(text) and text[j] in 'abcdefgABCDEFGz':
                j += 1
            
            # Octave modifiers (optional)
            while j < len(text) and text[j] in ",\'":
                j += 1
            
            # Duration (optional digits)
            while j < len(text) and (text[j].isdigit() or text[j] == '/'):
                j += 1
            
            tokens.append(text[i:j])
            i = j
            continue
        
        # Skip other characters
        i += 1
    
    return tokens


def _parse_abc_token(token: str, unit_in_qn: float, has_trill: bool) -> List[Tuple[int, float, bool]]:
    """Parse a single ABC token (note or chord)."""
    notes = []
    
    # Handle chord [CEG] or [C4E4G4]
    if token.startswith('[') and token.endswith(']'):
        # Parse chord
        chord_content = token[1:-1]
        # Split into individual notes - ABC chords are just concatenated
        # Parse each note in the chord
        chord_notes = re.findall(r'[_=^]?[A-Ga-g][,\']?\d*', chord_content)
        for note_str in chord_notes:
            parsed = _parse_single_abc_note(note_str, unit_in_qn, has_trill)
            if parsed:
                notes.append(parsed)
        return notes
    
    # Handle rest
    if token.startswith('z'):
        return []  # Skip rests
    
    # Handle single note
    parsed = _parse_single_abc_note(token, unit_in_qn, has_trill)
    if parsed:
        notes.append(parsed)
    
    return notes


def _parse_single_abc_note(note_str: str, unit_in_qn: float, has_trill: bool) -> Optional[Tuple[int, float, bool]]:
    """Parse a single ABC note string."""
    if not note_str or note_str.startswith('z'):
        return None
    
    # Extract accidental, pitch, octave modifiers, and duration
    match = re.match(r'([_=^]?)([A-Ga-g])([,\']*)([\d/]*)', note_str)
    if not match:
        return None
    
    accidental_str, pitch_letter, octave_mods, duration_str = match.groups()
    
    # Calculate MIDI pitch
    pitch_map = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
    base_pitch = pitch_map[pitch_letter.lower()]
    
    # Determine octave
    # In ABC: C D E F G A B (uppercase) = octave 4
    #         c d e f g a b (lowercase) = octave 5
    #         C, = octave 3, C'' = octave 6, etc.
    if pitch_letter.isupper():
        octave = 4
    else:
        octave = 5
    
    # Adjust for octave modifiers
    octave += octave_mods.count("'") - octave_mods.count(",")
    
    # Handle accidentals
    accidental = 0
    if accidental_str == '^':
        accidental = 1
    elif accidental_str == '_':
        accidental = -1
    
    midi_pitch = (octave) * 12 + base_pitch + accidental
    
    # Calculate duration
    if not duration_str:
        # Default duration is 1 unit
        duration = unit_in_qn
    else:
        # Parse duration like "8" or "1/2"
        if '/' in duration_str:
            parts = duration_str.split('/')
            numerator = int(parts[0]) if parts[0] else 1
            denominator = int(parts[1]) if len(parts) > 1 and parts[1] else 2
            duration = unit_in_qn * (numerator / denominator)
        else:
            multiplier = int(duration_str)
            duration = unit_in_qn * multiplier
    
    return (midi_pitch, duration, has_trill)


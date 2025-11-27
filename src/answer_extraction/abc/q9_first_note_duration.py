"""
Q9: What is the duration of the first note in the lower staff?

If there are multiple simultaneous notes, respond with the duration of the 
highest note. Respond in the number of quarter notes (e.g., 2 for a half note).

Rules:
- Find first NOTE (not rest) in lower staff
- If chord, all notes have same duration (report highest pitch's duration)
- Handle tuplets, broken rhythm, ties
- Count tied notes as one note with combined duration
- Return N/A if no notes in lower staff
"""

import re
from .utils import (
    get_lower_staff_voices, 
    extract_voice_content, 
    remove_non_note_elements,
    parse_unit_note_length,
    parse_duration_suffix,
    extract_chord_duration,
)
from ..core.duration import format_duration
from ..registry import register_extractor


def get_first_note_duration_in_content(content: str, unit_length: float) -> float | None:
    """
    Get the duration of the first note in ABC content.
    
    Handles tuplets, broken rhythm, and ties.
    For chords, returns the chord's duration (all notes same duration).
    Skips rests.
    
    Args:
        content: ABC notation content for a voice
        unit_length: Default note length in quarter notes
        
    Returns:
        Duration in quarter notes, or None if no notes found
    """
    # Remove non-note elements
    content = remove_non_note_elements(content)
    
    # Handle multiple layers (separated by &)
    layers = content.split('&')
    
    # Track first note duration across all layers
    first_durations = []
    
    for layer in layers:
        layer = layer.strip()
        if not layer:
            continue
        
        duration = _get_first_note_duration_single_layer(layer, unit_length)
        if duration is not None:
            first_durations.append(duration)
    
    if not first_durations:
        return None
    
    # Return the first occurring note's duration
    # (In simultaneous layers, they start at the same time, so any would be valid)
    return first_durations[0]


def _get_first_note_duration_single_layer(content: str, unit_length: float) -> float | None:
    """
    Get first note duration from a single voice layer.
    """
    # Tuplet tracking
    tuplet_ratio = 1.0
    tuplet_notes_remaining = 0
    
    # Broken rhythm tracking
    pending_broken_adjustment = None
    
    i = 0
    while i < len(content):
        char = content[i]
        
        # Skip whitespace
        if char in ' \t\n':
            i += 1
            continue
        
        # Skip barlines
        if char == '|':
            i += 1
            continue
        
        # Handle tuplets: (3, (5, (3:2:6, etc.
        if char == '(' and i + 1 < len(content) and content[i + 1].isdigit():
            i += 1
            # Parse tuplet number
            tuplet_num = int(content[i])
            i += 1
            
            # Check for complex tuplet syntax (p:q:r)
            if i < len(content) and content[i] == ':':
                i += 1
                # Parse q (time)
                if i < len(content) and content[i].isdigit():
                    q = int(content[i])
                    i += 1
                    tuplet_ratio = q / tuplet_num
                    # Check for :r (count)
                    if i < len(content) and content[i] == ':':
                        i += 1
                        # Parse r (could be multi-digit)
                        r_str = ''
                        while i < len(content) and content[i].isdigit():
                            r_str += content[i]
                            i += 1
                        tuplet_notes_remaining = int(r_str) if r_str else tuplet_num
                    else:
                        tuplet_notes_remaining = tuplet_num
                else:
                    tuplet_ratio = 2.0 / tuplet_num
                    tuplet_notes_remaining = tuplet_num
            else:
                # Simple tuplet like (3
                if tuplet_num == 3:
                    tuplet_ratio = 2.0 / 3.0
                elif tuplet_num == 2:
                    tuplet_ratio = 3.0 / 2.0
                else:
                    tuplet_ratio = 2.0 / tuplet_num
                tuplet_notes_remaining = tuplet_num
            continue
        
        # Skip slurs and decorations
        if char in '()~.HTLMOPSuv':
            i += 1
            continue
        
        # Handle grace notes - extract duration of first grace note
        if char == '{':
            grace_end = content.find('}', i)
            if grace_end == -1:
                grace_end = len(content)
            grace_content = content[i+1:grace_end]
            
            # Parse first grace note duration
            grace_duration = _get_first_grace_note_duration(grace_content, unit_length)
            if grace_duration is not None:
                return grace_duration
            
            i = grace_end + 1
            continue
        
        # Handle chords: [CEG]
        if char == '[':
            chord_end = content.find(']', i)
            if chord_end == -1:
                chord_end = len(content)
            chord_content = content[i+1:chord_end]
            i = chord_end + 1
            
            # Check if this chord contains any notes (not just inline field)
            if ':' in chord_content and not any(c.upper() in 'ABCDEFG' for c in chord_content.split(':')[0]):
                # This is an inline field like [K:G], skip
                continue
            
            # Get duration
            dur_mult = extract_chord_duration(chord_content)
            if dur_mult == 1.0:
                dur_mult, i = parse_duration_suffix(content, i)
            
            # Check for broken rhythm
            broken_mult = 1.0
            if i < len(content) and content[i] == '>':
                pending_broken_adjustment = 0.5
                broken_mult = 1.5
                i += 1
            elif i < len(content) and content[i] == '<':
                pending_broken_adjustment = 1.5
                broken_mult = 0.5
                i += 1
            
            if pending_broken_adjustment is not None and broken_mult == 1.0:
                broken_mult = pending_broken_adjustment
                pending_broken_adjustment = None
            
            # Check for ties and accumulate duration
            total_duration = unit_length * dur_mult * tuplet_ratio * broken_mult
            
            # Handle ties - need to follow tied notes
            while i < len(content) and content[i] == '-':
                i += 1
                # Find next note/chord and add its duration
                tied_dur = _get_tied_note_duration(content, i, unit_length, tuplet_ratio)
                if tied_dur is not None:
                    total_duration += tied_dur[0]
                    i = tied_dur[1]
                else:
                    break
            
            return total_duration
        
        # Handle rests: z or x - skip them, they're not notes
        if char in 'zxZ':
            i += 1
            # Skip duration suffix
            while i < len(content) and content[i] in '0123456789/':
                i += 1
            
            # Check for broken rhythm
            if i < len(content) and content[i] == '>':
                pending_broken_adjustment = 0.5
                i += 1
            elif i < len(content) and content[i] == '<':
                pending_broken_adjustment = 1.5
                i += 1
            
            if tuplet_notes_remaining > 0:
                tuplet_notes_remaining -= 1
                if tuplet_notes_remaining == 0:
                    tuplet_ratio = 1.0
            continue
        
        # Skip accidentals (handled with note)
        if char in '^_=':
            i += 1
            continue
        
        # Handle notes: A-G, a-g
        if char.upper() in 'ABCDEFG':
            i += 1
            
            # Skip octave markers
            while i < len(content) and content[i] in "',":
                i += 1
            
            # Get duration
            dur_mult, i = parse_duration_suffix(content, i)
            
            # Check for broken rhythm
            broken_mult = 1.0
            if i < len(content) and content[i] == '>':
                pending_broken_adjustment = 0.5
                broken_mult = 1.5
                i += 1
            elif i < len(content) and content[i] == '<':
                pending_broken_adjustment = 1.5
                broken_mult = 0.5
                i += 1
            
            if pending_broken_adjustment is not None and broken_mult == 1.0:
                broken_mult = pending_broken_adjustment
                pending_broken_adjustment = None
            
            # Calculate base duration
            total_duration = unit_length * dur_mult * tuplet_ratio * broken_mult
            
            # Handle ties
            while i < len(content) and content[i] == '-':
                i += 1
                tied_dur = _get_tied_note_duration(content, i, unit_length, tuplet_ratio)
                if tied_dur is not None:
                    total_duration += tied_dur[0]
                    i = tied_dur[1]
                else:
                    break
            
            return total_duration
        
        i += 1
    
    return None


def _get_first_grace_note_duration(grace_content: str, unit_length: float) -> float | None:
    """
    Get the duration of the first grace note from grace note content.
    
    Grace note VISUAL duration algorithm (empirically verified with abcjs rendering):
    
    The L: field has NO effect on grace note beams - they are independent.
    The leading / (acciaccatura marker) only adds a visual slash, doesn't affect duration.
    
    BASE BEAMS:
    - Single grace note: 1 beam (8th note) = 0.5 quarter notes
    - Multiple grace notes: 2 beams (16th note) = 0.25 quarter notes
    
    MODIFIERS ON FIRST NOTE:
    - Each `/` after the pitch ADDS one beam: C/ = 3 beams, C// = 4 beams
    - Numeric duration (e.g., C2) SETS beams to 1 (8th note)
    - Mixed groups: each note gets its own modifier applied independently
    
    BEAM TO DURATION MAPPING:
    - 1 beam = 8th note = 0.5 quarter notes
    - 2 beams = 16th note = 0.25 quarter notes  
    - 3 beams = 32nd note = 0.125 quarter notes
    - 4 beams = 64th note = 0.0625 quarter notes
    
    Empirically verified with tests 1-20.
    
    Args:
        grace_content: Content between { and } braces
        unit_length: Default note length (not used for grace notes, kept for API compatibility)
        
    Returns:
        Duration in quarter notes, or None if no notes found
    """
    if not grace_content:
        return None
    
    # Parse grace notes and track modifiers for each
    grace_notes = []  # List of (slash_count, has_numeric) tuples
    
    i = 0
    # Skip leading acciaccatura marker (only affects visual slash, not duration)
    if i < len(grace_content) and grace_content[i] == '/':
        i += 1
    
    while i < len(grace_content):
        char = grace_content[i]
        
        # Skip whitespace, slurs, accidentals
        if char in ' \t\n()^_=':
            i += 1
            continue
        
        # Found a note
        if char.upper() in 'ABCDEFG':
            i += 1
            
            # Skip octave markers
            while i < len(grace_content) and grace_content[i] in "',":
                i += 1
            
            # Parse duration modifiers for this note
            slash_count = 0
            has_numeric = False
            
            while i < len(grace_content):
                if grace_content[i] == '/':
                    slash_count += 1
                    i += 1
                elif grace_content[i].isdigit():
                    has_numeric = True
                    # Skip all digits
                    while i < len(grace_content) and grace_content[i].isdigit():
                        i += 1
                else:
                    break
            
            grace_notes.append((slash_count, has_numeric))
            continue
        
        # Skip any other characters
        i += 1
    
    if not grace_notes:
        return None
    
    # Get the first note's modifiers
    first_slash_count, first_has_numeric = grace_notes[0]
    note_count = len(grace_notes)
    
    # Determine base beams
    if note_count == 1:
        base_beams = 1  # Single grace = 8th note
    else:
        base_beams = 2  # Multiple graces = 16th note
    
    # Apply first note's modifiers
    if first_has_numeric:
        # Numeric duration (e.g., C2) sets beams to 1
        beams = 1
    else:
        # Each slash adds one beam
        beams = base_beams + first_slash_count
    
    # Convert beams to duration in quarter notes
    # 1 beam = 1/2, 2 beams = 1/4, 3 beams = 1/8, 4 beams = 1/16
    duration = 0.5 / (2 ** (beams - 1))
    
    return duration


def _get_tied_note_duration(content: str, start_idx: int, unit_length: float, 
                            tuplet_ratio: float) -> tuple[float, int] | None:
    """
    Get the duration of a tied note starting at start_idx.
    
    Returns (duration, new_index) or None if no note found.
    """
    i = start_idx
    
    # Skip whitespace
    while i < len(content) and content[i] in ' \t\n':
        i += 1
    
    # Skip accidentals
    while i < len(content) and content[i] in '^_=':
        i += 1
    
    if i >= len(content):
        return None
    
    char = content[i]
    
    # Handle chord
    if char == '[':
        chord_end = content.find(']', i)
        if chord_end == -1:
            return None
        chord_content = content[i+1:chord_end]
        i = chord_end + 1
        
        dur_mult = extract_chord_duration(chord_content)
        if dur_mult == 1.0:
            dur_mult, i = parse_duration_suffix(content, i)
        
        duration = unit_length * dur_mult * tuplet_ratio
        
        # Check for another tie
        if i < len(content) and content[i] == '-':
            # Leave tie for caller to handle
            pass
        
        return (duration, i)
    
    # Handle note
    if char.upper() in 'ABCDEFG':
        i += 1
        
        while i < len(content) and content[i] in "',":
            i += 1
        
        dur_mult, i = parse_duration_suffix(content, i)
        duration = unit_length * dur_mult * tuplet_ratio
        
        return (duration, i)
    
    return None


@register_extractor(9, "abc")
def extract(file_path: str) -> str:
    """
    Find the duration of the first note in lower staff.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The duration in quarter notes as a string
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Get lower staff voices
    lower_voices = get_lower_staff_voices(content)
    
    if not lower_voices:
        return "N/A"
    
    # Get unit note length
    unit_length = parse_unit_note_length(content)
    
    # Find first note duration across lower staff voices
    for voice_num in lower_voices:
        voice_content = extract_voice_content(content, voice_num)
        duration = get_first_note_duration_in_content(voice_content, unit_length)
        if duration is not None:
            return format_duration(duration)
    
    return "N/A"

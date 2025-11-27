"""
ABC notation parsing utilities.

Shared functions for parsing ABC notation files, extracting voice content,
counting notes, and handling the various ABC notation constructs.
"""

import re
from typing import List, Set, Tuple, Optional, Dict

# Import format-agnostic utilities from core
from ..core.pitch import pitch_to_midi, calculate_interval_semitones
from ..core.duration import format_duration


# Key signature definitions: maps key name to set of altered notes
# Sharps are uppercase, flats are lowercase in the key name
KEY_SIGNATURES: Dict[str, Dict[str, str]] = {
    # Major keys
    'C': {},
    'G': {'F': '#'},
    'D': {'F': '#', 'C': '#'},
    'A': {'F': '#', 'C': '#', 'G': '#'},
    'E': {'F': '#', 'C': '#', 'G': '#', 'D': '#'},
    'B': {'F': '#', 'C': '#', 'G': '#', 'D': '#', 'A': '#'},
    'F#': {'F': '#', 'C': '#', 'G': '#', 'D': '#', 'A': '#', 'E': '#'},
    'C#': {'F': '#', 'C': '#', 'G': '#', 'D': '#', 'A': '#', 'E': '#', 'B': '#'},
    'F': {'B': 'b'},
    'Bb': {'B': 'b', 'E': 'b'},
    'Eb': {'B': 'b', 'E': 'b', 'A': 'b'},
    'Ab': {'B': 'b', 'E': 'b', 'A': 'b', 'D': 'b'},
    'Db': {'B': 'b', 'E': 'b', 'A': 'b', 'D': 'b', 'G': 'b'},
    'Gb': {'B': 'b', 'E': 'b', 'A': 'b', 'D': 'b', 'G': 'b', 'C': 'b'},
    'Cb': {'B': 'b', 'E': 'b', 'A': 'b', 'D': 'b', 'G': 'b', 'C': 'b', 'F': 'b'},
    # Minor keys (same accidentals as relative major)
    'Am': {},
    'Em': {'F': '#'},
    'Bm': {'F': '#', 'C': '#'},
    'F#m': {'F': '#', 'C': '#', 'G': '#'},
    'C#m': {'F': '#', 'C': '#', 'G': '#', 'D': '#'},
    'G#m': {'F': '#', 'C': '#', 'G': '#', 'D': '#', 'A': '#'},
    'D#m': {'F': '#', 'C': '#', 'G': '#', 'D': '#', 'A': '#', 'E': '#'},
    'A#m': {'F': '#', 'C': '#', 'G': '#', 'D': '#', 'A': '#', 'E': '#', 'B': '#'},
    'Dm': {'B': 'b'},
    'Gm': {'B': 'b', 'E': 'b'},
    'Cm': {'B': 'b', 'E': 'b', 'A': 'b'},
    'Fm': {'B': 'b', 'E': 'b', 'A': 'b', 'D': 'b'},
    'Bbm': {'B': 'b', 'E': 'b', 'A': 'b', 'D': 'b', 'G': 'b'},
    'Ebm': {'B': 'b', 'E': 'b', 'A': 'b', 'D': 'b', 'G': 'b', 'C': 'b'},
    'Abm': {'B': 'b', 'E': 'b', 'A': 'b', 'D': 'b', 'G': 'b', 'C': 'b', 'F': 'b'},
}


def parse_staves_directive(content: str) -> List[List[str]]:
    """
    Parse the %%staves directive to determine staff groupings.
    
    Returns a list of staff groups, where each group is a list of voice numbers.
    The first group is the upper staff, the last group is the lower staff.
    
    Examples:
        "%%staves {1 2}" -> [["1"], ["2"]]
        "%%staves {(1 2) 3}" -> [["1", "2"], ["3"]]
        "%%staves {1 (2 3)}" -> [["1"], ["2", "3"]]
    
    Returns:
        List of staff groups (each group is a list of voice number strings)
    """
    match = re.search(r'%%staves\s*\{([^}]+)\}', content)
    if not match:
        # Fallback: assume voices 1 and 2 on separate staves
        return [["1"], ["2"]]
    
    staves_content = match.group(1).strip()
    
    staff_groups = []
    i = 0
    
    while i < len(staves_content):
        char = staves_content[i]
        
        # Skip whitespace
        if char in ' \t':
            i += 1
            continue
        
        # Handle grouped voices: (1 2)
        if char == '(':
            # Find closing paren
            paren_end = staves_content.find(')', i)
            if paren_end == -1:
                paren_end = len(staves_content)
            
            group_content = staves_content[i+1:paren_end]
            voices = group_content.split()
            staff_groups.append(voices)
            
            i = paren_end + 1
            continue
        
        # Handle single voice number
        if char.isdigit():
            # Collect all digits
            voice_num = ""
            while i < len(staves_content) and staves_content[i].isdigit():
                voice_num += staves_content[i]
                i += 1
            staff_groups.append([voice_num])
            continue
        
        # Skip other characters
        i += 1
    
    return staff_groups if staff_groups else [["1"], ["2"]]


def get_upper_staff_voices(content: str) -> List[str]:
    """
    Get the voice number(s) that belong to the upper staff.
    
    Args:
        content: Full ABC file content
    
    Returns:
        List of voice numbers (as strings) for the upper staff
    """
    staff_groups = parse_staves_directive(content)
    return staff_groups[0] if staff_groups else ["1"]


def get_lower_staff_voices(content: str) -> List[str]:
    """
    Get the voice number(s) that belong to the lower staff.
    
    Args:
        content: Full ABC file content
    
    Returns:
        List of voice numbers (as strings) for the lower staff
    """
    staff_groups = parse_staves_directive(content)
    return staff_groups[-1] if staff_groups else ["2"]


def extract_voice_content(content: str, voice_num: str) -> str:
    """
    Extract the musical content for a specific voice.
    
    Handles:
    - [V:n] inline voice markers
    - Multiple voices on same staff separated by &
    - Content continues until next [V:] marker or end of line
    
    Args:
        content: Full ABC file content
        voice_num: The voice number to extract (as string)
    
    Returns:
        The musical content for that voice
    """
    lines = content.split('\n')
    voice_content = []
    
    for line in lines:
        # Look for [V:n] markers
        if f'[V:{voice_num}]' in line:
            # Extract content after [V:n] marker up to barline or end
            match = re.search(rf'\[V:{voice_num}\]\s*(.*?)(?:\||$)', line)
            if match:
                voice_content.append(match.group(1))
    
    return ' '.join(voice_content)


def remove_non_note_elements(content: str) -> str:
    """
    Remove elements that should not be counted as notes.
    
    Removes:
    - Inline field markers like [K:clef=bass]
    - Annotations and text
    """
    # Remove inline field markers [X:...]
    content = re.sub(r'\[[A-Za-z]:[^\]]*\]', '', content)
    
    # Remove text annotations "..."
    content = re.sub(r'"[^"]*"', '', content)
    
    return content


def extract_pitches_from_chord(chord_content: str) -> List[str]:
    """
    Extract individual pitches from chord content (without brackets).
    
    E.g., "C4E4G4" -> ["C", "E", "G"] (with their accidentals and octave markers)
    
    Args:
        chord_content: Content between [ and ] in a chord
    
    Returns:
        List of pitch strings
    """
    pitches = []
    i = 0
    
    while i < len(chord_content):
        char = chord_content[i]
        
        # Skip non-note characters
        if char in ' \t':
            i += 1
            continue
        
        # Handle accidental + note
        if char in '^_=':
            accidental = char
            i += 1
            if i < len(chord_content) and chord_content[i].upper() in 'ABCDEFG':
                note = chord_content[i]
                i += 1
                # Get octave markers
                octave = ""
                while i < len(chord_content) and chord_content[i] in ",'":
                    octave += chord_content[i]
                    i += 1
                # Skip duration
                while i < len(chord_content) and (chord_content[i].isdigit() or chord_content[i] == '/'):
                    i += 1
                pitches.append(accidental + note + octave)
            continue
        
        # Handle note without accidental
        if char.upper() in 'ABCDEFG':
            note = char
            i += 1
            # Get octave markers
            octave = ""
            while i < len(chord_content) and chord_content[i] in ",'":
                octave += chord_content[i]
                i += 1
            # Skip duration
            while i < len(chord_content) and (chord_content[i].isdigit() or chord_content[i] == '/'):
                i += 1
            pitches.append(note + octave)
            continue
        
        # Skip other characters
        i += 1
    
    return pitches


def normalize_pitch(pitch: str) -> str:
    """
    Normalize a pitch for tie comparison.
    
    Ties connect notes of the same pitch. The accidental from the first note
    carries over, so we strip accidentals for comparison purposes.
    We keep octave markers (case and ,') since they affect which note is tied.
    
    Args:
        pitch: Pitch string with optional accidentals and octave markers
    
    Returns:
        Normalized pitch string (note letter + octave markers, no accidentals)
    """
    # Strip leading accidentals (^, _, =, ^^, __)
    normalized = pitch.lstrip('^_=')
    return normalized


def count_note_letters(content: str) -> int:
    """
    Simple count of note letters (A-G, a-g) in content.
    Used for grace notes where we don't need tie tracking.
    
    Args:
        content: ABC notation content
    
    Returns:
        Count of note letters
    """
    count = 0
    for char in content:
        if char.upper() in 'ABCDEFG':
            count += 1
    return count


def count_notes_in_single_voice(content: str) -> int:
    """
    Count notes in a single voice section of ABC content.
    
    This handles tie tracking to ensure tied notes are only counted once.
    
    Args:
        content: ABC notation content for a single voice
    
    Returns:
        Note count
    """
    count = 0
    
    # Track active ties
    active_ties: Set[str] = set()
    
    i = 0
    while i < len(content):
        char = content[i]
        
        # Skip whitespace
        if char in ' \t\n':
            i += 1
            continue
        
        # Handle grace notes: {/...} or {...}
        if char == '{':
            grace_end = content.find('}', i)
            if grace_end == -1:
                grace_end = len(content)
            grace_content = content[i+1:grace_end]
            
            # Grace notes may have / prefix for acciaccatura
            grace_content = grace_content.lstrip('/')
            count += count_note_letters(grace_content)
            
            i = grace_end + 1
            continue
        
        # Handle chords: [...]
        if char == '[':
            chord_end = content.find(']', i)
            if chord_end == -1:
                chord_end = len(content)
            chord_content = content[i+1:chord_end]
            
            chord_notes = extract_pitches_from_chord(chord_content)
            
            for pitch in chord_notes:
                normalized = normalize_pitch(pitch)
                if normalized in active_ties:
                    active_ties.discard(normalized)
                else:
                    count += 1
            
            # Check if there's a tie after the chord
            # Need to skip: duration digits, /, and rhythm modifiers like > <
            after_chord = chord_end + 1
            while after_chord < len(content) and content[after_chord] in '0123456789/<>':
                after_chord += 1
            
            if after_chord < len(content) and content[after_chord] == '-':
                for pitch in chord_notes:
                    active_ties.add(normalize_pitch(pitch))
            
            i = chord_end + 1
            continue
        
        # Handle tuplet markers: (3, (5, etc.
        if char == '(':
            if i + 1 < len(content) and content[i+1].isdigit():
                i += 1
                while i < len(content) and (content[i].isdigit() or content[i] == ':'):
                    i += 1
                continue
            else:
                i += 1
                continue
        
        # Skip closing slur/paren
        if char == ')':
            i += 1
            continue
        
        # Skip articulation markers, barlines, etc.
        if char in '.|><!~HTLMOPSuv':
            i += 1
            continue
        
        # Skip tie symbol
        if char == '-':
            i += 1
            continue
        
        # Handle rests - don't count them
        if char in 'zx':
            i += 1
            while i < len(content) and (content[i].isdigit() or content[i] == '/'):
                i += 1
            continue
        
        # Handle accidentals before notes
        if char in '^_=':
            i += 1
            continue
        
        # Handle actual notes: A-G and a-g
        if char.upper() in 'ABCDEFG':
            note_letter = char
            i += 1
            
            # Collect octave markers
            octave_markers = ""
            while i < len(content) and content[i] in ",'":
                octave_markers += content[i]
                i += 1
            
            # Skip duration and rhythm modifiers (> <)
            while i < len(content) and content[i] in '0123456789/<>':
                i += 1
            
            # Build pitch representation for tie tracking
            # Look back for accidentals
            accidental = ""
            j = i - len(octave_markers) - 2  # Position before note letter
            # Actually we need to track this differently - accidentals were skipped
            # For simplicity, just use note + octave for now
            
            pitch = note_letter + octave_markers
            normalized = normalize_pitch(pitch)
            
            if normalized in active_ties:
                active_ties.discard(normalized)
            else:
                count += 1
            
            # Check for tie (immediately after duration/rhythm modifiers)
            if i < len(content) and content[i] == '-':
                active_ties.add(normalized)
                i += 1
            
            continue
        
        # Skip any other character
        i += 1
    
    return count


def count_notes_in_content(content: str) -> int:
    """
    Count notes in ABC notation content.
    
    Handles multiple voices on same staff (separated by &).
    
    Args:
        content: ABC notation content (may contain multiple voices with &)
    
    Returns:
        Total note count
    """
    # Remove non-note elements first
    content = remove_non_note_elements(content)
    
    # Handle multiple voices on same staff (separated by &)
    voice_sections = content.split('&')
    
    total_count = 0
    for section in voice_sections:
        total_count += count_notes_in_single_voice(section)
    
    return total_count


def count_notes_for_voices(content: str, voice_nums: List[str]) -> int:
    """
    Count total notes across multiple voices.
    
    Args:
        content: Full ABC file content
        voice_nums: List of voice numbers to count
    
    Returns:
        Total note count across all specified voices
    """
    total = 0
    for voice_num in voice_nums:
        voice_content = extract_voice_content(content, voice_num)
        total += count_notes_in_content(voice_content)
    return total


def parse_key_signature(content: str) -> Dict[str, str]:
    """
    Parse the key signature from ABC content.
    
    Args:
        content: Full ABC file content
    
    Returns:
        Dictionary mapping note letters (A-G) to their accidentals ('#' or 'b')
    """
    # Look for K: field (either at line start or inline)
    # Handle both "K: Eb" and "K:Eb" formats
    match = re.search(r'K:\s*([A-Ga-g][#b]?)\s*(m(?:in(?:or)?)?|maj(?:or)?)?', content)
    if not match:
        return {}
    
    key_root = match.group(1)
    mode = match.group(2) or ''
    
    # Normalize key: capitalize first letter
    key_name = key_root[0].upper()
    if len(key_root) > 1:
        key_name += key_root[1]  # Keep # or b as-is
    
    # Add 'm' suffix for minor keys
    if mode.startswith('m'):
        key_name += 'm'
    
    return KEY_SIGNATURES.get(key_name, {})


def abc_pitch_to_scientific(abc_pitch: str, key_signature: Dict[str, str], 
                            active_accidentals: Optional[Dict[str, str]] = None) -> str:
    """
    Convert an ABC notation pitch to scientific pitch notation.
    
    ABC octave convention:
    - C, D, E, F, G, A, B = C4, D4, E4, F4, G4, A4, B4 (middle octave)
    - c, d, e, f, g, a, b = C5, D5, E5, F5, G5, A5, B5 (one octave higher)
    - C, = C3, C,, = C2, etc.
    - c' = C6, c'' = C7, etc.
    
    Args:
        abc_pitch: ABC pitch string (e.g., "^F", "c'", "_B,")
        key_signature: Dictionary of key signature accidentals
        active_accidentals: Optional dict of in-measure accidentals that override key sig.
                           Keys are like "G,3" (note + octave), values are '#', 'b', '##', 'bb', or ''
    
    Returns:
        Scientific pitch notation (e.g., "F#4", "C6", "Bb3")
    """
    if active_accidentals is None:
        active_accidentals = {}
    
    # Parse explicit accidental
    explicit_accidental = None  # None means no explicit accidental
    accidental_str = ''
    i = 0
    
    # Handle double accidentals
    if abc_pitch.startswith('^^'):
        explicit_accidental = '##'
        accidental_str = '^^'
        i = 2
    elif abc_pitch.startswith('__'):
        explicit_accidental = 'bb'
        accidental_str = '__'
        i = 2
    elif abc_pitch.startswith('^'):
        explicit_accidental = '#'
        accidental_str = '^'
        i = 1
    elif abc_pitch.startswith('_'):
        explicit_accidental = 'b'
        accidental_str = '_'
        i = 1
    elif abc_pitch.startswith('='):
        explicit_accidental = ''  # Natural - explicitly no accidental
        accidental_str = '='
        i = 1
    
    if i >= len(abc_pitch):
        return ''
    
    note_char = abc_pitch[i]
    i += 1
    
    # Determine base octave from case
    note_letter = note_char.upper()
    if note_char.islower():
        octave = 5  # c = C5
    else:
        octave = 4  # C = C4
    
    # Parse octave modifiers
    while i < len(abc_pitch):
        if abc_pitch[i] == "'":
            octave += 1
            i += 1
        elif abc_pitch[i] == ",":
            octave -= 1
            i += 1
        else:
            break
    
    # Build pitch key for active accidentals lookup (note letter + octave)
    pitch_key = f"{note_letter}{octave}"
    
    # Determine final accidental:
    # 1. If explicit accidental, use it
    # 2. Else if there's an active in-measure accidental for this pitch, use it
    # 3. Else use key signature
    if explicit_accidental is not None:
        final_accidental = explicit_accidental
    elif pitch_key in active_accidentals:
        final_accidental = active_accidentals[pitch_key]
    else:
        final_accidental = key_signature.get(note_letter, '')
    
    return f"{note_letter}{final_accidental}{octave}"


def get_pitch_key_from_abc(abc_pitch: str) -> Tuple[str, int]:
    """
    Extract the note letter and octave from an ABC pitch string.
    
    Args:
        abc_pitch: ABC pitch string (e.g., "^F", "c'", "_B,")
    
    Returns:
        Tuple of (note_letter uppercase, octave number)
    """
    i = 0
    # Skip accidentals
    while i < len(abc_pitch) and abc_pitch[i] in '^_=':
        i += 1
        if i < len(abc_pitch) and abc_pitch[i] == abc_pitch[i-1] and abc_pitch[i-1] in '^_':
            i += 1  # Double accidental
    
    if i >= len(abc_pitch):
        return ('', 0)
    
    note_char = abc_pitch[i]
    i += 1
    
    note_letter = note_char.upper()
    if note_char.islower():
        octave = 5
    else:
        octave = 4
    
    while i < len(abc_pitch):
        if abc_pitch[i] == "'":
            octave += 1
            i += 1
        elif abc_pitch[i] == ",":
            octave -= 1
            i += 1
        else:
            break
    
    return (note_letter, octave)


def get_accidental_from_abc(abc_pitch: str) -> Optional[str]:
    """
    Extract the accidental from an ABC pitch string.
    
    Returns:
        '#', '##', 'b', 'bb', '' (for natural), or None if no explicit accidental
    """
    if abc_pitch.startswith('^^'):
        return '##'
    elif abc_pitch.startswith('__'):
        return 'bb'
    elif abc_pitch.startswith('^'):
        return '#'
    elif abc_pitch.startswith('_'):
        return 'b'
    elif abc_pitch.startswith('='):
        return ''  # Natural
    return None


# pitch_to_midi is imported from ..core.pitch


def extract_first_pitch_from_content(content: str, key_signature: Dict[str, str]) -> Optional[str]:
    """
    Extract the first pitch from ABC content.
    
    If there are multiple simultaneous notes (chord or multiple voices with &),
    returns the highest pitch.
    
    Args:
        content: ABC notation content for a voice
        key_signature: Dictionary of key signature accidentals
    
    Returns:
        Scientific pitch notation of first note, or None if no notes found
    """
    # Remove non-note elements
    content = remove_non_note_elements(content)
    
    # Handle multiple voices on same staff (separated by &)
    voice_sections = content.split('&')
    
    # Get first pitch from each voice section
    first_pitches = []
    for section in voice_sections:
        pitch = _extract_first_pitch_single_voice(section, key_signature)
        if pitch:
            first_pitches.append(pitch)
    
    if not first_pitches:
        return None
    
    # Return highest pitch
    first_pitches.sort(key=lambda p: pitch_to_midi(p), reverse=True)
    return first_pitches[0]


def _extract_first_pitch_single_voice(content: str, key_signature: Dict[str, str]) -> Optional[str]:
    """
    Extract the first pitch from a single voice section.
    
    Args:
        content: ABC notation content for a single voice
        key_signature: Dictionary of key signature accidentals
    
    Returns:
        Scientific pitch notation of first note, or None if no notes found
    """
    i = 0
    
    while i < len(content):
        char = content[i]
        
        # Skip whitespace
        if char in ' \t\n':
            i += 1
            continue
        
        # Handle grace notes: {/...} or {...}
        # Grace notes count as first notes
        if char == '{':
            grace_end = content.find('}', i)
            if grace_end == -1:
                grace_end = len(content)
            grace_content = content[i+1:grace_end]
            
            # Grace notes may have / prefix for acciaccatura
            grace_content = grace_content.lstrip('/')
            
            # Extract first pitch from grace notes
            pitch = _extract_first_pitch_single_voice(grace_content, key_signature)
            if pitch:
                return pitch
            
            i = grace_end + 1
            continue
        
        # Handle chords: [...] - return highest pitch
        if char == '[':
            chord_end = content.find(']', i)
            if chord_end == -1:
                chord_end = len(content)
            chord_content = content[i+1:chord_end]
            
            chord_pitches = extract_pitches_from_chord(chord_content)
            if chord_pitches:
                # Convert all to scientific and find highest
                scientific_pitches = [abc_pitch_to_scientific(p, key_signature) for p in chord_pitches]
                scientific_pitches = [p for p in scientific_pitches if p]  # Filter empty
                if scientific_pitches:
                    scientific_pitches.sort(key=lambda p: pitch_to_midi(p), reverse=True)
                    return scientific_pitches[0]
            
            i = chord_end + 1
            continue
        
        # Handle tuplet markers: (3, (5, etc. - skip
        if char == '(':
            if i + 1 < len(content) and content[i+1].isdigit():
                i += 1
                while i < len(content) and (content[i].isdigit() or content[i] == ':'):
                    i += 1
                continue
            else:
                i += 1
                continue
        
        # Skip closing slur/paren
        if char == ')':
            i += 1
            continue
        
        # Skip articulation markers, barlines, etc.
        if char in '.|><!~HTLMOPSuv':
            i += 1
            continue
        
        # Skip tie symbol (shouldn't appear before first note anyway)
        if char == '-':
            i += 1
            continue
        
        # Handle rests - skip them, they're not notes
        if char in 'zx':
            i += 1
            while i < len(content) and (content[i].isdigit() or content[i] == '/'):
                i += 1
            continue
        
        # Handle accidentals before notes
        if char in '^_=':
            # Collect full accidental (could be ^^ or __)
            accidental = char
            i += 1
            if i < len(content) and content[i] == char and char in '^_':
                accidental += content[i]
                i += 1
            
            # Now get the note
            if i < len(content) and content[i].upper() in 'ABCDEFG':
                note_char = content[i]
                i += 1
                
                # Collect octave markers
                octave_markers = ""
                while i < len(content) and content[i] in ",'":
                    octave_markers += content[i]
                    i += 1
                
                abc_pitch = accidental + note_char + octave_markers
                return abc_pitch_to_scientific(abc_pitch, key_signature)
            continue
        
        # Handle actual notes: A-G and a-g
        if char.upper() in 'ABCDEFG':
            note_char = char
            i += 1
            
            # Collect octave markers
            octave_markers = ""
            while i < len(content) and content[i] in ",'":
                octave_markers += content[i]
                i += 1
            
            abc_pitch = note_char + octave_markers
            return abc_pitch_to_scientific(abc_pitch, key_signature)
        
        # Skip any other character
        i += 1
    
    return None


def get_first_pitch_for_voices(content: str, voice_nums: List[str]) -> Optional[str]:
    """
    Get the first pitch across multiple voices.
    
    Since all voices start at the same time, if there are notes in multiple
    voices at the start, we return the highest pitch.
    
    Args:
        content: Full ABC file content
        voice_nums: List of voice numbers to check
    
    Returns:
        Scientific pitch notation of highest first pitch, or None
    """
    key_signature = parse_key_signature(content)
    
    first_pitches = []
    for voice_num in voice_nums:
        voice_content = extract_voice_content(content, voice_num)
        pitch = extract_first_pitch_from_content(voice_content, key_signature)
        if pitch:
            first_pitches.append(pitch)
    
    if not first_pitches:
        return None
    
    # Return highest pitch
    first_pitches.sort(key=lambda p: pitch_to_midi(p), reverse=True)
    return first_pitches[0]


class NoteWithTiming:
    """Represents a note with its pitch and end time."""
    def __init__(self, pitch: str, end_time: float):
        self.pitch = pitch  # Scientific pitch notation
        self.end_time = end_time  # End time in quarter notes from start


def _extract_notes_with_timing(content: str, key_signature: Dict[str, str], 
                                unit_length: float) -> List[NoteWithTiming]:
    """
    Extract all notes with their end times from a single voice layer.
    
    This properly tracks timing through the layer, handling:
    - Duration suffixes
    - Broken rhythm (> and <)
    - Tuplets
    - Chords (all notes have same timing)
    - Rests (they advance time but aren't notes)
    - Grace notes (they don't advance time)
    
    Args:
        content: ABC notation content for a single voice layer
        key_signature: Dictionary of key signature accidentals
        unit_length: Default note length in quarter notes
        
    Returns:
        List of NoteWithTiming objects
    """
    notes: List[NoteWithTiming] = []
    current_time = 0.0
    
    # Track active accidentals within measure
    active_accidentals: Dict[str, str] = {}
    
    # For tuplets
    tuplet_ratio = 1.0
    tuplet_notes_remaining = 0
    
    # For broken rhythm
    pending_broken_adjustment: Optional[float] = None  # Multiplier for next note
    
    # Remove comments and non-essential elements
    content = remove_non_note_elements(content)
    
    i = 0
    while i < len(content):
        char = content[i]
        
        # Skip whitespace
        if char in ' \t\n':
            i += 1
            continue
        
        # Barline resets accidentals
        if char == '|':
            active_accidentals.clear()
            i += 1
            continue
        
        # Handle tuplets: (3, (5, etc.
        if char == '(' and i + 1 < len(content) and content[i + 1].isdigit():
            tuplet_num = int(content[i + 1])
            # Common tuplet ratios
            if tuplet_num == 3:
                tuplet_ratio = 2.0 / 3.0
                tuplet_notes_remaining = 3
            elif tuplet_num == 5:
                tuplet_ratio = 4.0 / 5.0
                tuplet_notes_remaining = 5
            elif tuplet_num == 6:
                tuplet_ratio = 4.0 / 6.0
                tuplet_notes_remaining = 6
            elif tuplet_num == 7:
                tuplet_ratio = 4.0 / 7.0
                tuplet_notes_remaining = 7
            else:
                tuplet_ratio = 2.0 / float(tuplet_num)
                tuplet_notes_remaining = tuplet_num
            i += 2
            continue
        
        # Skip slurs and other decorations
        if char in '()~.HTLMOPSuv':
            i += 1
            continue
        
        # Handle grace notes - extract pitches but don't advance time
        if char == '{':
            grace_end = content.find('}', i)
            if grace_end == -1:
                grace_end = len(content)
            grace_content = content[i+1:grace_end]
            # Skip leading / in acciaccatura
            if grace_content.startswith('/'):
                grace_content = grace_content[1:]
            
            # Extract grace note pitches (they have time 0, so end_time = current_time)
            grace_notes = _extract_pitches_with_timing_from_segment(
                grace_content, key_signature, active_accidentals, 
                unit_length, tuplet_ratio, current_time
            )
            notes.extend(grace_notes)
            
            i = grace_end + 1
            continue
        
        # Handle chords: [CEG]
        if char == '[':
            chord_end = content.find(']', i)
            if chord_end == -1:
                chord_end = len(content)
            chord_content = content[i+1:chord_end]
            i = chord_end + 1
            
            # Get duration after chord
            dur_mult = extract_chord_duration(chord_content)
            if dur_mult == 1.0:
                dur_mult, i = parse_duration_suffix(content, i)
            
            # Check for broken rhythm after duration
            broken_mult = 1.0
            if i < len(content) and content[i] == '>':
                pending_broken_adjustment = 0.5  # Next note gets 0.5x
                broken_mult = 1.5  # This note gets 1.5x
                i += 1
            elif i < len(content) and content[i] == '<':
                pending_broken_adjustment = 1.5
                broken_mult = 0.5
                i += 1
            
            # Apply pending broken rhythm from previous note
            if pending_broken_adjustment is not None and broken_mult == 1.0:
                broken_mult = pending_broken_adjustment
                pending_broken_adjustment = None
            
            # Calculate duration
            duration = unit_length * dur_mult * tuplet_ratio * broken_mult
            end_time = current_time + duration
            
            # Extract pitches from chord
            chord_pitches = extract_pitches_from_chord(chord_content)
            for abc_pitch in chord_pitches:
                sci_pitch = abc_pitch_to_scientific(abc_pitch, key_signature, active_accidentals)
                if sci_pitch:
                    notes.append(NoteWithTiming(sci_pitch, end_time))
                    # Update active accidentals
                    accidental = get_accidental_from_abc(abc_pitch)
                    if accidental is not None:
                        note_letter, octave = get_pitch_key_from_abc(abc_pitch)
                        if note_letter:
                            pitch_key = f"{note_letter}{octave}"
                            active_accidentals[pitch_key] = accidental
            
            current_time = end_time
            
            if tuplet_notes_remaining > 0:
                tuplet_notes_remaining -= 1
                if tuplet_notes_remaining == 0:
                    tuplet_ratio = 1.0
            
            continue
        
        # Handle rests: z or x
        if char in 'zx':
            i += 1
            dur_mult, i = parse_duration_suffix(content, i)
            
            # Apply broken rhythm if pending
            broken_mult = 1.0
            if pending_broken_adjustment is not None:
                broken_mult = pending_broken_adjustment
                pending_broken_adjustment = None
            
            # Check for broken rhythm after rest
            if i < len(content) and content[i] == '>':
                pending_broken_adjustment = 0.5
                broken_mult *= 1.5
                i += 1
            elif i < len(content) and content[i] == '<':
                pending_broken_adjustment = 1.5
                broken_mult *= 0.5
                i += 1
            
            duration = unit_length * dur_mult * tuplet_ratio * broken_mult
            current_time += duration
            
            if tuplet_notes_remaining > 0:
                tuplet_notes_remaining -= 1
                if tuplet_notes_remaining == 0:
                    tuplet_ratio = 1.0
            
            continue
        
        # Handle accidentals
        if char in '^_=':
            # Just continue, accidentals are handled with the note
            i += 1
            continue
        
        # Handle notes: A-G, a-g
        if char.upper() in 'ABCDEFG':
            # Collect accidentals before note
            accidental_prefix = ''
            j = i - 1
            while j >= 0 and content[j] in '^_=':
                accidental_prefix = content[j] + accidental_prefix
                j -= 1
            
            note_char = char
            i += 1
            
            # Collect octave markers
            octave_markers = ''
            while i < len(content) and content[i] in "',":
                octave_markers += content[i]
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
            
            # Apply pending broken rhythm
            if pending_broken_adjustment is not None and broken_mult == 1.0:
                broken_mult = pending_broken_adjustment
                pending_broken_adjustment = None
            
            # Check for tie (just skip it, we're not combining tied notes here)
            if i < len(content) and content[i] == '-':
                i += 1
            
            # Calculate duration
            duration = unit_length * dur_mult * tuplet_ratio * broken_mult
            end_time = current_time + duration
            
            # Convert to scientific pitch
            abc_pitch = accidental_prefix + note_char + octave_markers
            sci_pitch = abc_pitch_to_scientific(abc_pitch, key_signature, active_accidentals)
            
            if sci_pitch:
                notes.append(NoteWithTiming(sci_pitch, end_time))
                
                # Update active accidentals
                accidental = get_accidental_from_abc(abc_pitch)
                if accidental is not None:
                    note_letter, octave = get_pitch_key_from_abc(abc_pitch)
                    if note_letter:
                        pitch_key = f"{note_letter}{octave}"
                        active_accidentals[pitch_key] = accidental
            
            current_time = end_time
            
            if tuplet_notes_remaining > 0:
                tuplet_notes_remaining -= 1
                if tuplet_notes_remaining == 0:
                    tuplet_ratio = 1.0
            
            continue
        
        i += 1
    
    return notes


def _extract_pitches_with_timing_from_segment(content: str, key_signature: Dict[str, str],
                                               active_accidentals: Dict[str, str],
                                               unit_length: float, tuplet_ratio: float,
                                               current_time: float) -> List[NoteWithTiming]:
    """
    Extract pitches from a segment (like grace notes) without advancing time.
    All notes get the same end_time (current_time).
    """
    notes: List[NoteWithTiming] = []
    i = 0
    
    while i < len(content):
        char = content[i]
        
        if char in ' \t\n^_=':
            i += 1
            continue
        
        if char.upper() in 'ABCDEFG':
            # Collect accidentals before note
            accidental_prefix = ''
            j = i - 1
            while j >= 0 and content[j] in '^_=':
                accidental_prefix = content[j] + accidental_prefix
                j -= 1
            
            note_char = char
            i += 1
            
            # Collect octave markers
            octave_markers = ''
            while i < len(content) and content[i] in "',":
                octave_markers += content[i]
                i += 1
            
            # Skip duration for grace notes
            while i < len(content) and content[i] in '0123456789/<>-':
                i += 1
            
            abc_pitch = accidental_prefix + note_char + octave_markers
            sci_pitch = abc_pitch_to_scientific(abc_pitch, key_signature, active_accidentals)
            
            if sci_pitch:
                notes.append(NoteWithTiming(sci_pitch, current_time))
            
            continue
        
        i += 1
    
    return notes


def get_last_pitch_for_voices(content: str, voice_nums: List[str]) -> Optional[str]:
    """
    Get the last pitch across multiple voices.
    
    Properly tracks timing to find the note(s) that end latest.
    If multiple notes end at the same time, returns the highest pitch.
    
    Handles:
    - Multiple voice layers (separated by &)
    - All duration modifiers (suffixes, broken rhythm, tuplets)
    - Rests (they advance time but aren't considered as notes)
    - Chords (all notes have same end time)
    - Grace notes (they have end time = start time of next note)
    
    Args:
        content: Full ABC file content
        voice_nums: List of voice numbers to check
    
    Returns:
        Scientific pitch notation of the last note (highest if tie), or None
    """
    key_signature = parse_key_signature(content)
    unit_length = parse_unit_note_length(content)
    
    all_notes: List[NoteWithTiming] = []
    
    for voice_num in voice_nums:
        voice_content = extract_voice_content(content, voice_num)
        
        # Handle multiple layers (separated by &)
        voice_sections = voice_content.split('&')
        
        for section in voice_sections:
            section = section.strip()
            if not section:
                continue
            
            layer_notes = _extract_notes_with_timing(section, key_signature, unit_length)
            all_notes.extend(layer_notes)
    
    if not all_notes:
        return None
    
    # Find maximum end time
    max_end_time = max(note.end_time for note in all_notes)
    
    # Get all notes that end at or very close to max time (allow small float tolerance)
    tolerance = 0.001
    last_notes = [note for note in all_notes 
                  if abs(note.end_time - max_end_time) < tolerance]
    
    # Return highest pitch among last notes
    last_notes.sort(key=lambda n: pitch_to_midi(n.pitch), reverse=True)
    return last_notes[0].pitch


def extract_all_pitches_from_content(content: str, key_signature: Dict[str, str]) -> List[str]:
    """
    Extract ALL pitches from ABC content as scientific notation.
    
    Handles chords, grace notes, and multiple voice layers (separated by &).
    
    Args:
        content: ABC notation content for a voice
        key_signature: Dictionary of key signature accidentals
    
    Returns:
        List of all pitches in scientific notation
    """
    # Remove non-note elements
    content = remove_non_note_elements(content)
    
    # Handle multiple voices on same staff (separated by &)
    voice_sections = content.split('&')
    
    all_pitches = []
    for section in voice_sections:
        pitches = _extract_all_pitches_single_voice(section, key_signature)
        all_pitches.extend(pitches)
    
    return all_pitches


def _extract_all_pitches_single_voice(content: str, key_signature: Dict[str, str]) -> List[str]:
    """
    Extract all pitches from a single voice section.
    
    Handles in-measure accidental persistence: an accidental applies to all 
    subsequent notes of the same pitch within the same measure, until a barline.
    
    Args:
        content: ABC notation content for a single voice
        key_signature: Dictionary of key signature accidentals
    
    Returns:
        List of pitches in scientific notation
    """
    pitches = []
    i = 0
    
    # Track active accidentals within current measure
    # Keys are "NoteOctave" like "G3", values are '#', 'b', '##', 'bb', or '' (natural)
    active_accidentals: Dict[str, str] = {}
    
    while i < len(content):
        char = content[i]
        
        # Skip whitespace
        if char in ' \t\n':
            i += 1
            continue
        
        # Barline resets accidentals
        if char == '|':
            active_accidentals.clear()
            i += 1
            continue
        
        # Handle grace notes: {/...} or {...}
        if char == '{':
            grace_end = content.find('}', i)
            if grace_end == -1:
                grace_end = len(content)
            grace_content = content[i+1:grace_end]
            
            # Grace notes may have / prefix for acciaccatura
            grace_content = grace_content.lstrip('/')
            
            # Grace notes share the same active_accidentals context
            grace_pitches = _extract_pitches_with_accidentals(
                grace_content, key_signature, active_accidentals
            )
            pitches.extend(grace_pitches)
            
            i = grace_end + 1
            continue
        
        # Handle chords: [...]
        if char == '[':
            chord_end = content.find(']', i)
            if chord_end == -1:
                chord_end = len(content)
            chord_content = content[i+1:chord_end]
            
            chord_abc_pitches = extract_pitches_from_chord(chord_content)
            for abc_pitch in chord_abc_pitches:
                # Update active accidentals if this pitch has an explicit accidental
                explicit_acc = get_accidental_from_abc(abc_pitch)
                if explicit_acc is not None:
                    note_letter, octave = get_pitch_key_from_abc(abc_pitch)
                    if note_letter:
                        pitch_key = f"{note_letter}{octave}"
                        active_accidentals[pitch_key] = explicit_acc
                
                scientific = abc_pitch_to_scientific(abc_pitch, key_signature, active_accidentals)
                if scientific:
                    pitches.append(scientific)
            
            i = chord_end + 1
            continue
        
        # Handle tuplet markers: (3, (5, etc. - skip
        if char == '(':
            if i + 1 < len(content) and content[i+1].isdigit():
                i += 1
                while i < len(content) and (content[i].isdigit() or content[i] == ':'):
                    i += 1
                continue
            else:
                i += 1
                continue
        
        # Skip closing slur/paren
        if char == ')':
            i += 1
            continue
        
        # Skip articulation markers (but NOT barlines - handled above)
        if char in '.><!~HTLMOPSuv-':
            i += 1
            continue
        
        # Handle rests - skip them
        if char in 'zx':
            i += 1
            while i < len(content) and (content[i].isdigit() or content[i] == '/'):
                i += 1
            continue
        
        # Handle accidentals before notes
        if char in '^_=':
            # Collect full accidental (could be ^^ or __)
            accidental = char
            i += 1
            if i < len(content) and content[i] == char and char in '^_':
                accidental += content[i]
                i += 1
            
            # Now get the note
            if i < len(content) and content[i].upper() in 'ABCDEFG':
                note_char = content[i]
                i += 1
                
                # Collect octave markers
                octave_markers = ""
                while i < len(content) and content[i] in ",'":
                    octave_markers += content[i]
                    i += 1
                
                # Skip duration
                while i < len(content) and content[i] in '0123456789/<>':
                    i += 1
                
                abc_pitch = accidental + note_char + octave_markers
                
                # Update active accidentals
                note_letter, octave = get_pitch_key_from_abc(abc_pitch)
                if note_letter:
                    pitch_key = f"{note_letter}{octave}"
                    explicit_acc = get_accidental_from_abc(abc_pitch)
                    if explicit_acc is not None:
                        active_accidentals[pitch_key] = explicit_acc
                
                scientific = abc_pitch_to_scientific(abc_pitch, key_signature, active_accidentals)
                if scientific:
                    pitches.append(scientific)
            continue
        
        # Handle actual notes: A-G and a-g
        if char.upper() in 'ABCDEFG':
            note_char = char
            i += 1
            
            # Collect octave markers
            octave_markers = ""
            while i < len(content) and content[i] in ",'":
                octave_markers += content[i]
                i += 1
            
            # Skip duration
            while i < len(content) and content[i] in '0123456789/<>':
                i += 1
            
            abc_pitch = note_char + octave_markers
            scientific = abc_pitch_to_scientific(abc_pitch, key_signature, active_accidentals)
            if scientific:
                pitches.append(scientific)
            continue
        
        # Skip any other character
        i += 1
    
    return pitches


def _extract_pitches_with_accidentals(content: str, key_signature: Dict[str, str],
                                       active_accidentals: Dict[str, str]) -> List[str]:
    """
    Extract pitches from content, sharing an active_accidentals context.
    
    Used for grace notes which share accidental context with surrounding notes.
    
    Args:
        content: ABC notation content
        key_signature: Dictionary of key signature accidentals  
        active_accidentals: Mutable dict of in-measure accidentals (will be updated)
    
    Returns:
        List of pitches in scientific notation
    """
    pitches = []
    i = 0
    
    while i < len(content):
        char = content[i]
        
        if char in ' \t\n':
            i += 1
            continue
        
        # Handle accidentals before notes
        if char in '^_=':
            accidental = char
            i += 1
            if i < len(content) and content[i] == char and char in '^_':
                accidental += content[i]
                i += 1
            
            if i < len(content) and content[i].upper() in 'ABCDEFG':
                note_char = content[i]
                i += 1
                
                octave_markers = ""
                while i < len(content) and content[i] in ",'":
                    octave_markers += content[i]
                    i += 1
                
                while i < len(content) and content[i] in '0123456789/<>':
                    i += 1
                
                abc_pitch = accidental + note_char + octave_markers
                
                note_letter, octave = get_pitch_key_from_abc(abc_pitch)
                if note_letter:
                    pitch_key = f"{note_letter}{octave}"
                    explicit_acc = get_accidental_from_abc(abc_pitch)
                    if explicit_acc is not None:
                        active_accidentals[pitch_key] = explicit_acc
                
                scientific = abc_pitch_to_scientific(abc_pitch, key_signature, active_accidentals)
                if scientific:
                    pitches.append(scientific)
            continue
        
        if char.upper() in 'ABCDEFG':
            note_char = char
            i += 1
            
            octave_markers = ""
            while i < len(content) and content[i] in ",'":
                octave_markers += content[i]
                i += 1
            
            while i < len(content) and content[i] in '0123456789/<>':
                i += 1
            
            abc_pitch = note_char + octave_markers
            scientific = abc_pitch_to_scientific(abc_pitch, key_signature, active_accidentals)
            if scientific:
                pitches.append(scientific)
            continue
        
        i += 1
    
    return pitches


def get_lowest_pitch_for_voices(content: str, voice_nums: List[str]) -> Optional[str]:
    """
    Get the lowest pitch across all notes in multiple voices.
    
    Scans ALL notes (including grace notes, chords, multiple voice layers)
    in all specified voices and returns the one with the lowest MIDI number.
    
    Args:
        content: Full ABC file content
        voice_nums: List of voice numbers to check
    
    Returns:
        Scientific pitch notation of lowest pitch, or None if no notes found
    """
    key_signature = parse_key_signature(content)
    
    all_pitches = []
    for voice_num in voice_nums:
        voice_content = extract_voice_content(content, voice_num)
        pitches = extract_all_pitches_from_content(voice_content, key_signature)
        all_pitches.extend(pitches)
    
    if not all_pitches:
        return None
    
    # Return lowest pitch (minimum MIDI number)
    all_pitches.sort(key=lambda p: pitch_to_midi(p))
    return all_pitches[0]


# =============================================================================
# Duration Parsing Utilities
# =============================================================================

def parse_unit_note_length(content: str) -> float:
    """
    Parse the L: field to get the default note length in quarter notes.
    
    Args:
        content: Full ABC file content
    
    Returns:
        Default note length in quarter notes (e.g., 0.25 for L:1/16, 0.5 for L:1/8)
    """
    match = re.search(r'L:\s*(\d+)/(\d+)', content)
    if match:
        numerator = int(match.group(1))
        denominator = int(match.group(2))
        # Convert to quarter notes: 1/4 = 1, 1/8 = 0.5, 1/16 = 0.25
        return (numerator / denominator) * 4
    # Default to 1/8 if not specified
    return 0.5


def parse_duration_suffix(content: str, start_idx: int) -> Tuple[float, int]:
    """
    Parse duration suffix after a note (e.g., "2", "4", "/2", "3/2").
    
    Args:
        content: ABC content string
        start_idx: Index to start parsing from
    
    Returns:
        Tuple of (multiplier, end_index)
        multiplier is applied to the unit note length
    """
    i = start_idx
    
    # Collect the duration string
    duration_str = ""
    while i < len(content) and (content[i].isdigit() or content[i] == '/'):
        duration_str += content[i]
        i += 1
    
    if not duration_str:
        return (1.0, start_idx)
    
    # Parse the duration
    if '/' in duration_str:
        parts = duration_str.split('/')
        if parts[0] == '':
            # "/2" or "/" means divide by something
            numerator = 1
        else:
            numerator = int(parts[0])
        
        if len(parts) > 1 and parts[1]:
            denominator = int(parts[1])
        else:
            # "/" alone or "2/" - default denominator is 2
            denominator = 2
        
        return (numerator / denominator, i)
    else:
        # Just a number like "2" or "4"
        return (float(duration_str), i)


def extract_chord_duration(chord_content: str) -> float:
    """
    Extract the duration multiplier from chord content.
    
    In ABC, chords like [C4E4G4] have duration on each note (usually the same).
    We extract the duration from the first note that has one.
    
    Args:
        chord_content: Content between [ and ]
    
    Returns:
        Duration multiplier (default 1.0 if none found)
    """
    i = 0
    while i < len(chord_content):
        char = chord_content[i]
        
        # Skip accidentals
        if char in '^_=':
            i += 1
            if i < len(chord_content) and chord_content[i] == char and char in '^_':
                i += 1
            continue
        
        # Found a note letter
        if char.upper() in 'ABCDEFG':
            i += 1
            # Skip octave markers
            while i < len(chord_content) and chord_content[i] in ",'":
                i += 1
            # Now parse duration
            dur_mult, _ = parse_duration_suffix(chord_content, i)
            return dur_mult
        
        i += 1
    
    return 1.0


class NoteWithDuration:
    """Represents a note with its duration and tie status."""
    def __init__(self, pitch_key: str, duration: float, is_tied: bool):
        self.pitch_key = pitch_key  # Normalized pitch for tie matching
        self.duration = duration
        self.is_tied = is_tied  # True if this note has a tie to the next


def extract_all_durations_from_content(content: str, unit_length: float) -> List[float]:
    """
    Extract all note durations from ABC content.
    
    Handles:
    - Basic durations with suffixes
    - Broken rhythm (> and <)
    - Tuplets
    - Ties (sums tied note durations)
    - Excludes grace notes
    
    Args:
        content: ABC notation content for a voice
        unit_length: Default note length in quarter notes (from L: field)
    
    Returns:
        List of note durations in quarter notes (tied notes combined)
    """
    # Remove non-note elements but keep barlines for accidental tracking
    content = remove_non_note_elements(content)
    
    # Handle multiple voices on same staff (separated by &)
    voice_sections = content.split('&')
    
    all_durations = []
    for section in voice_sections:
        durations = _extract_durations_single_voice(section, unit_length)
        all_durations.extend(durations)
    
    return all_durations


def _extract_durations_single_voice(content: str, unit_length: float) -> List[float]:
    """
    Extract all note durations from a single voice section.
    
    Args:
        content: ABC notation content for a single voice
        unit_length: Default note length in quarter notes
    
    Returns:
        List of note durations in quarter notes
    """
    durations: List[float] = []
    
    # Track notes with ties for combining durations
    # Key: normalized pitch, Value: accumulated duration
    active_ties: Dict[str, float] = {}
    
    # Current tuplet ratio (1.0 = no tuplet)
    tuplet_ratio = 1.0
    tuplet_notes_remaining = 0
    
    # For broken rhythm
    pending_broken_rhythm: Optional[str] = None  # '>' or '<'
    last_note_duration_idx: Optional[int] = None  # Index in durations list
    
    i = 0
    while i < len(content):
        char = content[i]
        
        # Skip whitespace
        if char in ' \t\n':
            i += 1
            continue
        
        # Barline - doesn't affect durations
        if char == '|':
            i += 1
            continue
        
        # Skip grace notes entirely - they don't count
        if char == '{':
            grace_end = content.find('}', i)
            if grace_end == -1:
                grace_end = len(content)
            i = grace_end + 1
            continue
        
        # Handle tuplet markers: (3, (3:2:3, etc.
        if char == '(':
            if i + 1 < len(content) and content[i+1].isdigit():
                i += 1
                # Parse tuplet: (p:q:r or (p
                p = 0
                while i < len(content) and content[i].isdigit():
                    p = p * 10 + int(content[i])
                    i += 1
                
                q = None
                r = None
                
                if i < len(content) and content[i] == ':':
                    i += 1
                    q = 0
                    while i < len(content) and content[i].isdigit():
                        q = q * 10 + int(content[i])
                        i += 1
                    
                    if i < len(content) and content[i] == ':':
                        i += 1
                        r = 0
                        while i < len(content) and content[i].isdigit():
                            r = r * 10 + int(content[i])
                            i += 1
                
                # Default values based on p
                if q is None:
                    # Standard tuplet: p notes in the time of q
                    # For triplet (3): 3 notes in time of 2
                    if p in [2, 4, 8]:
                        q = 3
                    else:
                        q = 2
                
                if r is None:
                    r = p
                
                tuplet_ratio = q / p
                tuplet_notes_remaining = r
                continue
            else:
                # Regular slur, skip
                i += 1
                continue
        
        # Skip closing paren
        if char == ')':
            i += 1
            continue
        
        # Handle broken rhythm markers - apply to previous note and next note
        if char in '><':
            pending_broken_rhythm = char
            i += 1
            continue
        
        # Skip other articulation markers
        if char in '.!~HTLMOPSuv-':
            i += 1
            continue
        
        # Handle rests - they have duration but we track them separately
        if char in 'zx':
            i += 1
            # Parse duration
            dur_mult, i = parse_duration_suffix(content, i)
            # Rests don't count as notes for "longest note"
            # But we still need to track tuplet
            if tuplet_notes_remaining > 0:
                tuplet_notes_remaining -= 1
                if tuplet_notes_remaining == 0:
                    tuplet_ratio = 1.0
            continue
        
        # Handle chords: [...]
        if char == '[':
            chord_end = content.find(']', i)
            if chord_end == -1:
                chord_end = len(content)
            chord_content = content[i+1:chord_end]
            i = chord_end + 1
            
            # Duration can be inside the chord (on each note) OR after the bracket
            # First try to get duration from inside the chord
            dur_mult = extract_chord_duration(chord_content)
            
            # If no duration inside, check after bracket
            if dur_mult == 1.0:
                dur_mult_after, i = parse_duration_suffix(content, i)
                if dur_mult_after != 1.0:
                    dur_mult = dur_mult_after
            
            # Check for tie after chord
            is_tied = False
            # Skip any broken rhythm markers when looking for tie
            tie_check_idx = i
            while tie_check_idx < len(content) and content[tie_check_idx] in '><':
                tie_check_idx += 1
            if tie_check_idx < len(content) and content[tie_check_idx] == '-':
                is_tied = True
            
            # Calculate base duration
            base_duration = unit_length * dur_mult * tuplet_ratio
            
            # Get pitches from chord for tie tracking
            chord_pitches = extract_pitches_from_chord(chord_content)
            
            # Handle ties for each note in chord
            for pitch in chord_pitches:
                normalized = normalize_pitch(pitch)
                
                if normalized in active_ties:
                    # This note continues a tie
                    active_ties[normalized] += base_duration
                else:
                    # New note
                    active_ties[normalized] = base_duration
                
                if not is_tied:
                    # Tie ends, record final duration
                    durations.append(active_ties[normalized])
                    del active_ties[normalized]
            
            # Apply broken rhythm to last duration if pending
            if pending_broken_rhythm and last_note_duration_idx is not None:
                if pending_broken_rhythm == '>':
                    # Previous note gets 1.5x, this note gets 0.5x
                    durations[last_note_duration_idx] *= 1.5
                    if durations:  # Apply 0.5 to current notes
                        for j in range(len(durations) - len(chord_pitches), len(durations)):
                            if not is_tied:  # Only if we added durations
                                durations[j] *= 0.5
                else:  # '<'
                    durations[last_note_duration_idx] *= 0.5
                    if durations:
                        for j in range(len(durations) - len(chord_pitches), len(durations)):
                            if not is_tied:
                                durations[j] *= 1.5
                pending_broken_rhythm = None
            
            if not is_tied and durations:
                last_note_duration_idx = len(durations) - 1
            
            # Update tuplet counter
            if tuplet_notes_remaining > 0:
                tuplet_notes_remaining -= 1
                if tuplet_notes_remaining == 0:
                    tuplet_ratio = 1.0
            
            continue
        
        # Handle accidentals before notes (skip them, we just need duration)
        if char in '^_=':
            i += 1
            if i < len(content) and content[i] == char and char in '^_':
                i += 1  # Double accidental
            continue
        
        # Handle actual notes: A-G and a-g
        if char.upper() in 'ABCDEFG':
            note_start = i
            note_char = char
            i += 1
            
            # Collect octave markers
            octave_markers = ""
            while i < len(content) and content[i] in ",'":
                octave_markers += content[i]
                i += 1
            
            # Parse duration
            dur_mult, i = parse_duration_suffix(content, i)
            
            # Check for broken rhythm after duration
            if i < len(content) and content[i] in '><':
                # This is part of the current note pair
                pass  # Will be handled on next iteration
            
            # Check for tie
            is_tied = False
            tie_check_idx = i
            while tie_check_idx < len(content) and content[tie_check_idx] in '><':
                tie_check_idx += 1
            if tie_check_idx < len(content) and content[tie_check_idx] == '-':
                is_tied = True
            
            # Build pitch key for tie tracking
            pitch_key = note_char + octave_markers
            normalized = normalize_pitch(pitch_key)
            
            # Calculate duration
            base_duration = unit_length * dur_mult * tuplet_ratio
            
            if normalized in active_ties:
                # Continue tie
                active_ties[normalized] += base_duration
            else:
                # New note
                active_ties[normalized] = base_duration
            
            if not is_tied:
                # Tie ends (or no tie), record duration
                final_duration = active_ties[normalized]
                durations.append(final_duration)
                del active_ties[normalized]
                last_note_duration_idx = len(durations) - 1
            
            # Apply broken rhythm
            if pending_broken_rhythm and last_note_duration_idx is not None and len(durations) >= 2:
                prev_idx = last_note_duration_idx - 1 if not is_tied else last_note_duration_idx
                curr_idx = len(durations) - 1
                if prev_idx >= 0 and prev_idx != curr_idx:
                    if pending_broken_rhythm == '>':
                        durations[prev_idx] *= 1.5
                        durations[curr_idx] *= 0.5
                    else:
                        durations[prev_idx] *= 0.5
                        durations[curr_idx] *= 1.5
                pending_broken_rhythm = None
            
            # Update tuplet counter
            if tuplet_notes_remaining > 0:
                tuplet_notes_remaining -= 1
                if tuplet_notes_remaining == 0:
                    tuplet_ratio = 1.0
            
            continue
        
        # Skip any other character
        i += 1
    
    # Handle any remaining tied notes (ties that go to end of content)
    for pitch, duration in active_ties.items():
        durations.append(duration)
    
    return durations


def get_longest_duration(content: str) -> Optional[float]:
    """
    Get the longest note duration in the entire passage.
    
    Scans all voices in both staves and returns the maximum duration.
    
    Args:
        content: Full ABC file content
    
    Returns:
        Longest duration in quarter notes, rounded to nearest hundredth,
        or None if no notes found
    """
    unit_length = parse_unit_note_length(content)
    
    # Get all voices
    staff_groups = parse_staves_directive(content)
    all_voices = []
    for group in staff_groups:
        all_voices.extend(group)
    
    all_durations = []
    for voice_num in all_voices:
        voice_content = extract_voice_content(content, voice_num)
        durations = extract_all_durations_from_content(voice_content, unit_length)
        all_durations.extend(durations)
    
    if not all_durations:
        return None
    
    max_duration = max(all_durations)
    
    # Round to nearest hundredth
    rounded = round(max_duration, 2)
    
    # Return as int if it's a whole number
    if rounded == int(rounded):
        return int(rounded)
    
    return rounded
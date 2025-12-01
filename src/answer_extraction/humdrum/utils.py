"""
Humdrum (**kern) parsing utilities.

Shared functions for parsing Humdrum notation files, extracting spine content,
counting notes, and handling the various Humdrum notation constructs.

Humdrum **kern basics:
- Spines (columns) are tab-separated
- Leftmost **kern spine is typically bass/left hand (*staff2, *LH)
- Rightmost **kern spine is typically treble/right hand (*staff1, *RH)
- Notes: duration + pitch, e.g., "4c" = quarter note C
- Pitch case: uppercase = below middle C, lowercase = at/above middle C
- Double letters: higher octaves (cc = C5, ccc = C6)
- Accidentals: - = flat, # = sharp, n = natural
- Rests: r with duration, e.g., "4r" = quarter rest
- Chords: multiple notes in same spine separated by space
- Grace notes: q = acciaccatura (durationless), Q = gruppetto (has duration)
- Appoggiaturas: P = appoggiatura note, p = shortened following note
- Ties: [ = start, ] = end, _ = continuation

Spine path handling:
- *^ = split spine into two
- *v = merge adjacent spines
- *- = terminate spine
- *+ = add new spine
- *x = exchange adjacent spines

FUTURE ENHANCEMENTS for full movement support:
- Repeat expansion: Currently ignores *>[A,A,B,B] repeat markers. For full movements,
  need to expand repeated sections to get accurate note counts.
- Section markers: Handle *>A, *>B section labels for repeat navigation.
- First/second endings: Handle *>norep[A,B] and volta brackets.
- Multi-movement files: Handle !!!!SEGMENT markers for movement boundaries.
"""

import re
from typing import List, Tuple, Set, Optional, Dict
from dataclasses import dataclass

# Import format-agnostic utilities from core
from ..core.pitch import pitch_to_midi, calculate_interval_semitones
from ..core.duration import format_duration


@dataclass
class HumdrumNote:
    """Represents a single note parsed from Humdrum."""
    pitch: str          # Pitch name with octave (e.g., "C4", "F#5")
    duration: float     # Duration in quarter notes (1.0 = quarter, 0.5 = eighth)
    midi: int          # MIDI pitch number
    is_grace: bool     # Is this a grace note?
    is_tie_start: bool # Does this note start a tie?
    is_tie_end: bool   # Is this note the end of a tie?
    is_tie_cont: bool  # Is this a tie continuation?
    raw_token: str     # Original token from file


@dataclass 
class SpineInfo:
    """Tracks a spine and its descendants through spine path operations."""
    original_index: int      # Index in original **kern declaration
    staff: str              # "upper" or "lower"
    is_kern: bool           # Is this a **kern spine?
    

def parse_file_with_spine_tracking(file_path: str) -> Tuple[List[str], List[str]]:
    """
    Parse a Humdrum file with full spine path tracking.
    
    Properly handles spine splits (*^), merges (*v), exchanges (*x), 
    additions (*+), and terminations (*-).
    
    Returns:
        Tuple of (lower_staff_tokens, upper_staff_tokens)
        Each is a list of all data tokens from that staff.
    """
    with open(file_path, 'r') as f:
        lines = f.read().split('\n')
    
    lower_tokens = []
    upper_tokens = []
    
    # First, find the initial **kern spine positions
    kern_indices = []  # List of (column_index, staff_type)
    initial_spine_count = 0
    
    for line in lines:
        if line.startswith('**'):
            spines = line.split('\t')
            initial_spine_count = len(spines)
            for i, spine in enumerate(spines):
                if spine == '**kern':
                    kern_indices.append(i)
            break
    
    if len(kern_indices) < 1:
        return [], []
    
    # Determine which kern spine is lower (first) and upper (last)
    lower_original_idx = kern_indices[0]
    upper_original_idx = kern_indices[-1] if len(kern_indices) >= 2 else kern_indices[0]
    
    # Track active spine mappings: maps current column index to original kern index
    # Each entry: column_idx -> original_kern_idx (or -1 if not kern)
    spine_map = {}
    for i in range(initial_spine_count):
        if i in kern_indices:
            spine_map[i] = i
        else:
            spine_map[i] = -1  # Not a kern spine
    
    # Process file line by line
    for line in lines:
        line = line.rstrip()
        
        if not line:
            continue
            
        # Skip global comments
        if line.startswith('!!'):
            continue
            
        # Skip local comments
        if line.startswith('!') and not line.startswith('!!'):
            continue
        
        # Handle spine path interpretations
        if line.startswith('*'):
            tokens = line.split('\t')
            
            # Check for spine path operators
            has_path_op = any(t in ('*^', '*v', '*-', '*x') or t.startswith('*+') 
                             for t in tokens)
            
            if has_path_op:
                spine_map = _update_spine_map(tokens, spine_map, lower_original_idx, upper_original_idx)
            continue
        
        # Skip barlines
        if line.startswith('='):
            continue
        
        # Data line - extract tokens from appropriate spines
        tokens = line.split('\t')
        
        for col_idx, token in enumerate(tokens):
            if col_idx not in spine_map:
                continue
                
            original_idx = spine_map[col_idx]
            if original_idx == -1:
                continue  # Not a kern spine
                
            token = token.strip()
            if not token or token == '.':
                continue
                
            # Determine which staff this belongs to
            if original_idx == lower_original_idx:
                lower_tokens.append(token)
            if original_idx == upper_original_idx:
                upper_tokens.append(token)
    
    return lower_tokens, upper_tokens


def _update_spine_map(tokens: List[str], spine_map: Dict[int, int], 
                      lower_orig: int, upper_orig: int) -> Dict[int, int]:
    """
    Update spine map based on spine path operators.
    
    Handles: *^ (split), *v (merge), *- (terminate), *x (exchange), *+ (add)
    """
    new_map = {}
    new_col = 0
    i = 0
    
    while i < len(tokens):
        token = tokens[i]
        old_orig = spine_map.get(i, -1)
        
        if token == '*^':
            # Split: this column becomes two columns, both inherit the original
            new_map[new_col] = old_orig
            new_map[new_col + 1] = old_orig
            new_col += 2
            i += 1
            
        elif token == '*v':
            # Merge: consume all adjacent *v tokens, output one column
            # The merged column inherits from the first spine being merged
            merge_origins = [old_orig]
            j = i + 1
            while j < len(tokens) and tokens[j] == '*v':
                merge_origins.append(spine_map.get(j, -1))
                j += 1
            
            # The merged spine inherits from all original kern spines involved
            # Use the first non-negative original index, or keep all that match lower/upper
            kern_origins = [o for o in merge_origins if o != -1]
            if kern_origins:
                # If any of the merged spines was from lower, new one is lower
                # If any was from upper, new one is upper
                # We pick the first kern origin to preserve
                new_map[new_col] = kern_origins[0]
            else:
                new_map[new_col] = -1
            
            new_col += 1
            i = j  # Skip past all the *v tokens
            
        elif token == '*-':
            # Terminate: this spine disappears, don't add to new map
            i += 1
            
        elif token == '*x':
            # Exchange: swap with next column
            if i + 1 < len(tokens) and tokens[i + 1] == '*x':
                next_orig = spine_map.get(i + 1, -1)
                new_map[new_col] = next_orig
                new_map[new_col + 1] = old_orig
                new_col += 2
                i += 2
            else:
                # Invalid exchange, just pass through
                new_map[new_col] = old_orig
                new_col += 1
                i += 1
                
        elif token.startswith('*+'):
            # Add new spine: current column stays, new column inserted after
            new_map[new_col] = old_orig
            new_col += 1
            # The new spine is not a kern spine (it will get its ** in next record)
            new_map[new_col] = -1
            new_col += 1
            i += 1
            
        else:
            # Regular interpretation (*, *clefG2, etc.) - column passes through
            new_map[new_col] = old_orig
            new_col += 1
            i += 1
    
    return new_map


def get_lower_spine_data(file_path: str) -> List[str]:
    """
    Extract all data tokens from the lower (left-hand) staff.
    
    Properly handles spine splits, merges, and other spine path operations.
    Collects data from all spines that descended from the original lower staff.
    
    Returns:
        List of tokens from the lower staff
    """
    lower_tokens, _ = parse_file_with_spine_tracking(file_path)
    return lower_tokens


def get_upper_spine_data(file_path: str) -> List[str]:
    """
    Extract all data tokens from the upper (right-hand) staff.
    
    Properly handles spine splits, merges, and other spine path operations.
    Collects data from all spines that descended from the original upper staff.
    
    Returns:
        List of tokens from the upper staff
    """
    _, upper_tokens = parse_file_with_spine_tracking(file_path)
    return upper_tokens


def get_upper_spine_data_by_row(file_path: str) -> List[List[str]]:
    """
    Extract data tokens from the upper staff, grouped by row (time position).
    
    This preserves simultaneity information - tokens in the same inner list
    occur at the same time position (same row in the original file).
    This is essential for correctly handling spine splits where simultaneous
    notes appear in different columns.
    
    Returns:
        List of rows, where each row is a list of tokens occurring at that time
    """
    with open(file_path, 'r') as f:
        lines = f.read().split('\n')
    
    rows = []
    
    # First, find the initial **kern spine positions
    kern_indices = []
    initial_spine_count = 0
    
    for line in lines:
        if line.startswith('**'):
            spines = line.split('\t')
            initial_spine_count = len(spines)
            for i, spine in enumerate(spines):
                if spine == '**kern':
                    kern_indices.append(i)
            break
    
    if len(kern_indices) < 1:
        return []
    
    # Determine upper staff index (rightmost kern spine)
    upper_original_idx = kern_indices[-1] if len(kern_indices) >= 2 else kern_indices[0]
    
    # Track active spine mappings
    spine_map = {}
    for i in range(initial_spine_count):
        if i in kern_indices:
            spine_map[i] = i
        else:
            spine_map[i] = -1
    
    # Process file line by line
    for line in lines:
        line = line.rstrip()
        
        if not line or line.startswith('!!') or (line.startswith('!') and not line.startswith('!!')):
            continue
        
        # Handle spine path interpretations
        if line.startswith('*'):
            tokens = line.split('\t')
            has_path_op = any(t in ('*^', '*v', '*-', '*x') or t.startswith('*+') 
                             for t in tokens)
            if has_path_op:
                spine_map = _update_spine_map(tokens, spine_map, kern_indices[0], upper_original_idx)
            continue
        
        # Skip barlines
        if line.startswith('='):
            continue
        
        # Data line - collect all upper staff tokens from this row
        tokens = line.split('\t')
        row_tokens = []
        
        for col_idx, token in enumerate(tokens):
            if col_idx not in spine_map:
                continue
            original_idx = spine_map[col_idx]
            if original_idx != upper_original_idx:
                continue
            token = token.strip()
            if not token or token == '.':
                continue
            row_tokens.append(token)
        
        if row_tokens:
            rows.append(row_tokens)
    
    return rows


def is_rest(token: str) -> bool:
    """Check if a token is a rest."""
    # Remove any beam/articulation markers first
    cleaned = re.sub(r'[LJKk]', '', token)
    return 'r' in cleaned and not any(c in cleaned for c in 'abcdefgABCDEFG')


def is_invisible_rest(token: str) -> bool:
    """
    Check if a token is an invisible rest.
    
    In Humdrum, 'yy' suffix makes an element invisible/non-printing.
    Per the system prompt: "Only respond based on elements that will be 
    visually rendered in the score."
    """
    return is_rest(token) and 'yy' in token


def is_grace_note(token: str) -> bool:
    """
    Check if a token is a grace note (acciaccatura or gruppetto).
    
    In Humdrum:
    - q = acciaccatura (durationless grace note)  
    - Q = gruppetto (small note with notated duration)
    
    Both should be counted as notes.
    """
    # Check for lowercase 'q' (acciaccatura) - this is the most common
    # The token.lower() approach catches both q and Q
    return 'q' in token.lower()


def is_note(token: str) -> bool:
    """Check if a token contains a note (not a rest or null)."""
    if not token or token == '.':
        return False
    if is_rest(token):
        return False
    # Must contain a pitch letter
    return bool(re.search(r'[a-gA-G]', token))


def extract_notes_from_token(token: str) -> List[str]:
    """
    Extract individual note tokens from a spine token (may contain chords).
    
    Chords in Humdrum are space-separated notes within a spine.
    
    Args:
        token: A single spine data token
    
    Returns:
        List of individual note tokens
    """
    if not token or token == '.':
        return []
    
    # Split by space for chords
    parts = token.split()
    notes = []
    
    for part in parts:
        if is_note(part):
            notes.append(part)
    
    return notes


def parse_kern_pitch(token: str) -> Optional[str]:
    """
    Parse a **kern pitch token to standard pitch notation (e.g., "C4", "F#5").
    
    Kern pitch encoding:
    - Uppercase letters: octave below middle C (C3 and lower)
    - Lowercase letters: middle C octave and above (C4 and higher)
    - Repeated letters indicate higher/lower octaves
    - Accidentals: # = sharp, - = flat, n = natural
    
    Returns:
        Pitch in format "C4", "F#5", etc., or None if not a note
    """
    if not token or not is_note(token):
        return None
    
    # Extract the pitch portion (letters and accidentals)
    # Remove duration, beam markers, articulations, ties, etc.
    cleaned = re.sub(r'[\d./\[\]_LJKkMSsTtp<>!]', '', token)
    cleaned = re.sub(r'q+', '', cleaned)  # Remove grace note markers
    
    if not cleaned:
        return None
    
    # Find the pitch letters
    pitch_match = re.search(r'([a-gA-G]+)', cleaned)
    if not pitch_match:
        return None
    
    pitch_letters = pitch_match.group(1)
    
    # Determine base pitch and octave
    first_letter = pitch_letters[0]
    letter_count = len(pitch_letters)
    
    if first_letter.isupper():
        # Uppercase = octave 3 and below
        # C = C3, CC = C2, CCC = C1
        base_octave = 4 - letter_count  # C = 4-1 = 3, CC = 4-2 = 2
        pitch_name = first_letter.upper()
    else:
        # Lowercase = octave 4 and above
        # c = C4, cc = C5, ccc = C6
        base_octave = 3 + letter_count  # c = 3+1 = 4, cc = 3+2 = 5
        pitch_name = first_letter.upper()
    
    # Extract accidentals
    accidental = ''
    if '#' in cleaned:
        sharp_count = cleaned.count('#')
        accidental = '#' * sharp_count
    elif '-' in cleaned:
        flat_count = cleaned.count('-')
        # Use 'b' for display
        accidental = 'b' * flat_count
    # 'n' (natural) is implicit, we don't add it to the pitch name
    
    return f"{pitch_name}{accidental}{base_octave}"


def parse_kern_duration(token: str) -> float:
    """
    Parse a **kern duration to quarter note beats.
    
    Kern duration encoding:
    - Number represents reciprocal of whole note: 1=whole, 2=half, 4=quarter, 8=eighth
    - Dots add half the value: 4. = dotted quarter = 1.5 beats
    - Special: 0 = breve (double whole), 00 = longa
    - Triplets: 12 = triplet eighth (1/3 quarter), 6 = triplet quarter, 3 = triplet half
    
    Note: Tokens may have articulation/slur markers like ( ) at the start,
    so we use re.search instead of re.match.
    
    Returns:
        Duration in quarter note beats (1.0 = quarter note)
    """
    if not token:
        return 0.0
    
    # Extract duration number - use search to handle prefixes like ( or )
    dur_match = re.search(r'(\d+)', token)
    if not dur_match:
        return 1.0  # Default to quarter note
    
    dur_num = int(dur_match.group(1))
    
    # Convert to quarter note beats
    if dur_num == 0:
        base_duration = 8.0  # Breve = 2 whole notes = 8 quarter notes
    else:
        # dur_num is reciprocal of whole note
        # whole = 4 quarter notes, half = 2, quarter = 1, eighth = 0.5
        # triplets: 12 = 4/12 = 0.333, 6 = 4/6 = 0.667, 3 = 4/3 = 1.333
        base_duration = 4.0 / dur_num
    
    # Count dots
    dot_count = token.count('.')
    duration = base_duration
    dot_value = base_duration / 2
    for _ in range(dot_count):
        duration += dot_value
        dot_value /= 2
    
    return duration


def count_notes_in_spine(tokens: List[str], include_grace: bool = True) -> int:
    """
    Count notes in a list of spine tokens, handling ties correctly.
    
    Tied notes should only be counted once (at the start of the tie).
    However, for passages extracted from larger pieces, if a tie started
    BEFORE the passage (not in our tokens), we should still count the 
    tie-end/continuation note as a distinct note in this passage.
    
    Args:
        tokens: List of spine data tokens
        include_grace: Whether to include grace notes in the count
    
    Returns:
        Number of distinct notes
    """
    count = 0
    
    # Track pitches that have active ties (started with [)
    # Key: pitch string, Value: True if tie is active
    active_ties = set()
    
    for token in tokens:
        notes = extract_notes_from_token(token)
        
        for note in notes:
            # Skip grace notes if not including them
            if not include_grace and is_grace_note(note):
                continue
            
            pitch = parse_kern_pitch(note)
            
            # Check tie markers
            has_tie_start = '[' in note
            has_tie_end = ']' in note
            has_tie_cont = '_' in note
            
            if has_tie_start:
                # Note starts a tie - count it and mark tie as active
                active_ties.add(pitch)
                count += 1
            elif has_tie_end or has_tie_cont:
                # Tie end or continuation
                if pitch in active_ties:
                    # This tie started within our passage - don't count again
                    if has_tie_end:
                        active_ties.discard(pitch)
                    # Don't count - already counted at tie start
                else:
                    # This tie started BEFORE our passage - count it as a note
                    # (it's a note that sounds in this passage)
                    count += 1
                    if has_tie_end:
                        pass  # Tie ends, nothing to track
                    else:
                        # Continuation - might have more continuations
                        active_ties.add(pitch)
            else:
                # Regular note, no tie markers
                count += 1
    
    return count


def get_note_durations_with_ties(tokens: List[str], include_grace: bool = False) -> List[float]:
    """
    Get all note durations from spine tokens, summing tied notes into single durations.
    
    For tied notes, tracks each pitch's tie chain and returns the TOTAL duration
    when the tie ends. This ensures that a half note tied to a quarter (2.0 + 1.0)
    is returned as a single 3.0 duration.
    
    For ties that start before the passage (tie-end/continuation without a prior
    tie-start in our tokens), we still sum their visible portions.
    
    Args:
        tokens: List of spine data tokens
        include_grace: Whether to include grace notes (default: False, they're durationless)
    
    Returns:
        List of note durations in quarter notes, with tied notes summed
    """
    durations = []
    
    # Track active ties: pitch -> accumulated duration so far
    active_ties: Dict[str, float] = {}
    
    for token in tokens:
        notes = extract_notes_from_token(token)
        
        for note in notes:
            # Skip grace notes if not including them
            if not include_grace and is_grace_note(note):
                continue
            
            pitch = parse_kern_pitch(note)
            dur = parse_kern_duration(note)
            
            # Check tie markers
            has_tie_start = '[' in note
            has_tie_end = ']' in note
            has_tie_cont = '_' in note
            
            if has_tie_start:
                # Starting a new tie - begin accumulating duration
                active_ties[pitch] = dur
                # Don't add to durations yet - wait for tie end
            elif has_tie_end:
                # End of a tie - add accumulated duration + this note's duration
                if pitch in active_ties:
                    total_dur = active_ties[pitch] + dur
                    durations.append(total_dur)
                    del active_ties[pitch]
                else:
                    # Tie started before passage - just count this portion
                    durations.append(dur)
            elif has_tie_cont:
                # Tie continuation - accumulate duration
                if pitch in active_ties:
                    active_ties[pitch] += dur
                else:
                    # Tie started before passage - start accumulating
                    active_ties[pitch] = dur
            else:
                # Regular note, no tie markers - add directly
                durations.append(dur)
    
    # If there are still active ties at end of passage (tie continues beyond),
    # we should include their accumulated duration as they represent notes
    # in this passage
    for pitch, dur in active_ties.items():
        durations.append(dur)
    
    return durations


def count_rests_in_spine(tokens: List[str]) -> int:
    """
    Count visible rests in a list of spine tokens.
    
    Invisible rests (with 'yy' suffix) are excluded per the system prompt:
    "Only respond based on elements that will be visually rendered in the score."
    
    Args:
        tokens: List of spine data tokens
    
    Returns:
        Number of visible rests
    """
    count = 0
    
    for token in tokens:
        # Each part of the token (split by space) could be a rest
        parts = token.split()
        for part in parts:
            # Skip invisible rests (ryy)
            if is_rest(part) and not is_invisible_rest(part):
                count += 1
    
    return count


def get_all_pitches_in_spine(tokens: List[str], include_grace: bool = True) -> List[str]:
    """
    Extract all pitches from a spine as standardized pitch strings.
    
    Args:
        tokens: List of spine data tokens
        include_grace: Whether to include grace notes
    
    Returns:
        List of pitches in "C4" format
    """
    pitches = []
    
    for token in tokens:
        notes = extract_notes_from_token(token)
        
        for note in notes:
            if not include_grace and is_grace_note(note):
                continue
            
            pitch = parse_kern_pitch(note)
            if pitch:
                pitches.append(pitch)
    
    return pitches


def get_first_note_pitch(tokens: List[str], return_highest_in_chord: bool = True, include_grace: bool = True) -> Optional[str]:
    """
    Get the first note's pitch in the spine.
    
    Args:
        tokens: List of spine data tokens
        return_highest_in_chord: If True and first note is a chord, return highest pitch
        include_grace: If True, grace notes count as notes (default True per question wording)
    
    Returns:
        Pitch in "C4" format, or None if no notes found
    """
    for token in tokens:
        notes = extract_notes_from_token(token)
        
        # Filter based on include_grace setting
        if include_grace:
            candidate_notes = notes
        else:
            candidate_notes = [n for n in notes if not is_grace_note(n)]
        
        if not candidate_notes:
            continue
            
        if return_highest_in_chord and len(candidate_notes) > 1:
            # Find the highest pitch in the chord
            highest_midi = -1
            highest_pitch = None
            for note in candidate_notes:
                pitch = parse_kern_pitch(note)
                if pitch:
                    midi = pitch_to_midi(pitch)
                    if midi is not None and midi > highest_midi:
                        highest_midi = midi
                        highest_pitch = pitch
            if highest_pitch:
                return highest_pitch
        else:
            # Single note or just return first
            pitch = parse_kern_pitch(candidate_notes[0])
            if pitch:
                return pitch
    return None


def get_first_note_duration(tokens: List[str], include_grace: bool = True) -> Optional[str]:
    """
    Get the first note's duration as a formatted string.
    
    Per system prompt: "Always consider grace notes and ornaments to be the 
    same as normal notes."
    
    Args:
        tokens: List of spine data tokens
        include_grace: Whether to include grace notes (default True per system prompt)
    
    Returns:
        Formatted duration string (e.g., "0.5", "0.13")
    """
    for token in tokens:
        notes = extract_notes_from_token(token)
        for note in notes:
            # Skip grace notes only if explicitly told to
            if not include_grace and is_grace_note(note):
                continue
            
            duration = parse_kern_duration(note)
            if duration > 0:
                return format_duration(duration)
    return None


def get_lowest_pitch_in_spine(tokens: List[str]) -> Optional[str]:
    """
    Find the lowest pitch in the spine.
    
    Args:
        tokens: List of spine data tokens
    
    Returns:
        Lowest pitch in "C4" format
    """
    pitches = get_all_pitches_in_spine(tokens, include_grace=True)
    if not pitches:
        return None
    
    lowest_midi = float('inf')
    lowest_pitch = None
    
    for pitch in pitches:
        midi = pitch_to_midi(pitch)
        if midi is not None and midi < lowest_midi:
            lowest_midi = midi
            lowest_pitch = pitch
    
    return lowest_pitch


def get_longest_duration_in_spine(tokens: List[str]) -> Optional[str]:
    """
    Find the longest note duration in the spine.
    
    Args:
        tokens: List of spine data tokens
    
    Returns:
        Longest duration as formatted string
    """
    longest = 0.0
    
    for token in tokens:
        notes = extract_notes_from_token(token)
        for note in notes:
            # Skip grace notes
            if is_grace_note(note):
                continue
            
            duration = parse_kern_duration(note)
            if duration > longest:
                longest = duration
    
    if longest > 0:
        return format_duration(longest)
    return None


def get_pitch_classes_in_spine(tokens: List[str]) -> Set[str]:
    """
    Get all unique pitch classes (ignoring octave) in the spine.
    
    Args:
        tokens: List of spine data tokens
    
    Returns:
        Set of pitch class names like {"C", "D", "F#", "Bb"}
    """
    pitches = get_all_pitches_in_spine(tokens, include_grace=True)
    pitch_classes = set()
    
    for pitch in pitches:
        # Extract pitch class (letter + accidental, no octave number)
        match = re.match(r'([A-G][#b]*)', pitch)
        if match:
            pitch_classes.add(match.group(1))
    
    return pitch_classes


def get_interval_first_last(tokens: List[str], include_grace: bool = True) -> Optional[int]:
    """
    Calculate the interval in semitones between first and last notes.
    
    For multiple simultaneous notes (chords), picks the highest pitch.
    If there's only one note event (or first and last are the same event),
    returns 0 (unison).
    
    NOTE: This function treats each token as a separate event. For files with
    spine splits where simultaneous notes are in different tokens, use
    get_interval_first_last_by_rows() instead.
    
    Args:
        tokens: List of spine data tokens
        include_grace: Whether to include grace notes (default True per system prompt)
    
    Returns:
        Interval in semitones (absolute value - always positive or zero),
        or None if no notes at all
    """
    # Collect notes grouped by token (simultaneous notes)
    # Each element is a list of pitches from that token
    note_events = []
    
    for token in tokens:
        notes = extract_notes_from_token(token)
        event_pitches = []
        for note in notes:
            # Skip grace notes only if explicitly told to
            if not include_grace and is_grace_note(note):
                continue
            pitch = parse_kern_pitch(note)
            if pitch:
                event_pitches.append(pitch)
        if event_pitches:
            note_events.append(event_pitches)
    
    if not note_events:
        return None
    
    if len(note_events) == 1:
        # Only one note event - first and last are the same, interval is 0
        return 0
    
    # Get first event's highest pitch
    first_pitches = note_events[0]
    first_pitch = max(first_pitches, key=lambda p: pitch_to_midi(p))
    
    # Get last event's highest pitch
    last_pitches = note_events[-1]
    last_pitch = max(last_pitches, key=lambda p: pitch_to_midi(p))
    
    return calculate_interval_semitones(first_pitch, last_pitch)


def get_interval_first_last_by_rows(rows: List[List[str]], include_grace: bool = True) -> Optional[int]:
    """
    Calculate the interval in semitones between first and last notes using row-grouped data.
    
    This correctly handles spine splits where simultaneous notes appear in
    different tokens but at the same time position (same row).
    
    For multiple simultaneous notes, picks the highest pitch.
    If there's only one note event (or first and last are the same event),
    returns 0 (unison).
    
    Args:
        rows: List of rows, where each row is a list of tokens at that time position
        include_grace: Whether to include grace notes (default True per system prompt)
    
    Returns:
        Interval in semitones (absolute value - always positive or zero),
        or None if no notes at all
    """
    # Collect notes grouped by row (all tokens in a row are simultaneous)
    note_events = []
    
    for row in rows:
        event_pitches = []
        for token in row:
            notes = extract_notes_from_token(token)
            for note in notes:
                # Skip grace notes only if explicitly told to
                if not include_grace and is_grace_note(note):
                    continue
                # Skip rests
                if is_rest(note):
                    continue
                pitch = parse_kern_pitch(note)
                if pitch:
                    event_pitches.append(pitch)
        if event_pitches:
            note_events.append(event_pitches)
    
    if not note_events:
        return None
    
    if len(note_events) == 1:
        # Only one note event - first and last are the same, interval is 0
        return 0
    
    # Get first event's highest pitch
    first_pitches = note_events[0]
    first_pitch = max(first_pitches, key=lambda p: pitch_to_midi(p))
    
    # Get last event's highest pitch  
    last_pitches = note_events[-1]
    last_pitch = max(last_pitches, key=lambda p: pitch_to_midi(p))
    
    return calculate_interval_semitones(first_pitch, last_pitch)

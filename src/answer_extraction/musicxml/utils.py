"""
MusicXML parsing utilities.

Shared functions for parsing MusicXML files, extracting staff content,
counting notes, and handling the various MusicXML notation constructs.

MusicXML 3.1 basics (as used in these files):
- Partwise format: <score-partwise> contains <part> elements, each with <measure>s
- Staves: <staves>2</staves> in <attributes>, then <staff>1</staff> or <staff>2</staff> in notes
  - Staff 1 = upper staff (typically treble clef)
  - Staff 2 = lower staff (typically bass clef)
- Voices: <voice> element distinguishes independent melodic lines (1,2 for upper staff, 5,6 for lower)
- Notes: <note> elements with <pitch> (step, alter, octave), <duration>, <type>
- Chords: Subsequent <note> with <chord/> belongs to previous note's chord
- Grace notes: <grace/> element makes it a grace note (no <duration>)
- Ties: <tie type="start"/> and <tie type="stop"/> in note, with <tied> in <notations>
- Rests: <rest/> inside <note>
- Tuplets: <time-modification> with <actual-notes> and <normal-notes>
- Visibility: print-object="no" makes elements non-printing (should be excluded)
- Backup/Forward: <backup> and <forward> adjust timing for multiple voices
- Divisions: <divisions> in <attributes> defines duration units per quarter note

TIMING MODEL:
- Each note has a position in "divisions" from measure start
- We track position by processing notes sequentially and using <backup>/<forward>
- Grace notes don't advance time but belong to the position of the next regular note
- Chords share the same position

EDGE CASES HANDLED:
- Invisible notes/rests (print-object="no")
- Grace notes (included in counts, excluded from durations for Q5/Q9)
- Tied notes (count once, sum durations across tie chain)
- Tuplets (duration adjusted by time-modification)
- Multiple voices on same staff
- Cross-staff notes (notes with <staff> pointing to different staff, sorted after native notes)
- Both encoding styles: single-part with explicit staves AND separate parts (P1/P2)
- N/A returns when no valid notes exist

ENCODING STYLES:
1. Explicit staves: Single <part> with <staves>2</staves>, notes have <staff> elements
2. Separate parts: Two <part> elements (P1=upper, P2=lower), notes may have <staff> for cross-staff

FUTURE ENHANCEMENTS for full movement support:
- Repeat handling: <repeat> elements with direction="backward"/"forward"
- First/second endings: <ending> elements with type and number
- Codas and segnos: <coda>, <segno> elements
"""

import xml.etree.ElementTree as ET
from typing import List, Set, Optional, Dict, Tuple
from collections import defaultdict

# Import format-agnostic utilities from core
from ..core.pitch import pitch_to_midi, calculate_interval_semitones
from ..core.duration import format_duration


# ============================================================================
# CONSTANTS
# ============================================================================

# Staff identifiers (string values as they appear in MusicXML)
UPPER_STAFF = "1"  # Upper staff (typically treble clef)
LOWER_STAFF = "2"  # Lower staff (typically bass clef)

# Offset for cross-staff note document ordering
# When notes from one part have explicit <staff> elements pointing to another staff
# (cross-staff notation), they should sort after "native" notes at the same timestamp.
# This offset is added to doc_order for cross-staff notes to achieve proper ordering.
# Value is large enough to never conflict with real document order values.
# Used in _collect_notes_with_timing to sort cross-staff notes after native notes.
CROSS_STAFF_POSITION_OFFSET = 100000

# Grace notes get small position offsets to maintain document order
# This ensures grace notes before a beat sort correctly before that beat's notes
GRACE_NOTE_POSITION_INCREMENT = 0.0001

# MusicXML duration type to quarter note values (without dots)
# These are base values before dot modification
DURATION_TYPE_MAP = {
    'maxima': 32.0,      # 8 whole notes
    'long': 16.0,        # 4 whole notes  
    'breve': 8.0,        # 2 whole notes
    'whole': 4.0,        # Whole note
    'half': 2.0,         # Half note
    'quarter': 1.0,      # Quarter note
    'eighth': 0.5,       # Eighth note
    '16th': 0.25,        # 16th note
    '32nd': 0.125,       # 32nd note
    '64th': 0.0625,      # 64th note
    '128th': 0.03125,    # 128th note
    '256th': 0.015625,   # 256th note
    '512th': 0.0078125,  # 512th note
    '1024th': 0.00390625, # 1024th note
}

# Accidental alter values to symbols
ALTER_TO_SYMBOL = {
    -2: 'bb',
    -1: 'b',
    0: '',
    1: '#',
    2: '##',
}


# ============================================================================
# PARSING FUNCTIONS
# ============================================================================

def parse_musicxml_file(file_path: str) -> ET.Element:
    """
    Parse a MusicXML file and return the root element.
    
    Args:
        file_path: Path to the MusicXML file
        
    Returns:
        The root Element of the parsed XML tree
    """
    tree = ET.parse(file_path)
    return tree.getroot()


def is_visible(note: ET.Element) -> bool:
    """
    Check if a note/rest element is visible (should be printed/counted).
    
    MusicXML uses print-object="no" to hide elements.
    
    Args:
        note: A <note> element
        
    Returns:
        True if the note should be counted, False if it's invisible
    """
    return note.get("print-object") != "no"


def is_grace_note(note: ET.Element) -> bool:
    """
    Check if a note is a grace note.
    
    Grace notes have a <grace/> child element and no <duration>.
    
    Args:
        note: A <note> element
        
    Returns:
        True if this is a grace note
    """
    return note.find("grace") is not None


def is_rest(note: ET.Element) -> bool:
    """
    Check if a note element is actually a rest.
    
    In MusicXML, rests are encoded as <note> elements with a <rest/> child.
    
    Args:
        note: A <note> element
        
    Returns:
        True if this is a rest
    """
    return note.find("rest") is not None


def is_chord_note(note: ET.Element) -> bool:
    """
    Check if a note is part of a chord (not the first note of the chord).
    
    The first note of a chord has no <chord/> element.
    Subsequent notes in the chord have <chord/>.
    
    Args:
        note: A <note> element
        
    Returns:
        True if this is a chord continuation note
    """
    return note.find("chord") is not None


def get_note_staff(note: ET.Element) -> Optional[str]:
    """
    Get the staff number for a note if explicitly specified.
    
    Returns None if no <staff> element is present, allowing the caller
    to determine the default based on context (e.g., which part the note is in).
    
    Args:
        note: A <note> element
        
    Returns:
        Staff number as string ("1" or "2"), or None if not specified
    """
    staff_elem = note.find("staff")
    if staff_elem is not None and staff_elem.text:
        return staff_elem.text.strip()
    return None  # Let caller determine default


def get_note_voice(note: ET.Element) -> str:
    """
    Get the voice number for a note.
    
    Voices help distinguish independent melodic lines.
    Typically: 1-4 for upper staff, 5-8 for lower staff.
    
    Args:
        note: A <note> element
        
    Returns:
        Voice number as string
    """
    voice_elem = note.find("voice")
    if voice_elem is not None and voice_elem.text:
        return voice_elem.text.strip()
    return "1"  # Default to voice 1


def _uses_explicit_staves(root: ET.Element) -> bool:
    """
    Detect if the file uses explicit <staves> and <staff> elements.
    
    MusicXML files can organize piano/keyboard music in two ways:
    1. Single part with <staves>2</staves> and <staff> on each note
    2. Separate parts (P1 for RH, P2 for LH) without <staff> elements
    
    Args:
        root: The MusicXML root element
        
    Returns:
        True if file uses explicit staves, False if using separate parts
    """
    # Check if any part has <staves> attribute
    for part in root.iter("part"):
        for measure in part.iter("measure"):
            attrs = measure.find("attributes")
            if attrs is not None:
                staves = attrs.find("staves")
                if staves is not None and staves.text:
                    if int(staves.text.strip()) > 1:
                        return True
    return False


def _get_part_for_staff(root: ET.Element, staff_n: str) -> Optional[ET.Element]:
    """
    Get the primary part element corresponding to a staff for separate-parts encoding.
    
    In separate-parts encoding:
    - Staff "1" (upper) = first part
    - Staff "2" (lower) = second part
    
    Note: This returns the PRIMARY part for a staff. Cross-staff notes from other
    parts are handled by iterating all parts and checking <staff> elements.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number ("1" or "2")
        
    Returns:
        The part element, or None if not found
    """
    parts = list(root.iter("part"))
    if staff_n == UPPER_STAFF and len(parts) >= 1:
        return parts[0]
    elif staff_n == LOWER_STAFF and len(parts) >= 2:
        return parts[1]
    return None


def _get_default_staff_for_part(root: ET.Element, part: ET.Element) -> str:
    """
    Get the default staff number for a part in separate-parts encoding.
    
    First part defaults to staff "1", second part to staff "2".
    This is used when a note doesn't have an explicit <staff> element.
    
    Args:
        root: The MusicXML root element
        part: The part element
        
    Returns:
        Default staff number ("1" or "2")
    """
    parts = list(root.iter("part"))
    for i, p in enumerate(parts):
        if p is part:
            return UPPER_STAFF if i == 0 else LOWER_STAFF
    return UPPER_STAFF  # Default fallback


def _get_parts_for_staff(root: ET.Element, staff_n: str) -> List[ET.Element]:
    """
    Get the parts to iterate for a given staff.
    
    Handles both encoding styles:
    1. Explicit staves: Return all parts (filter by <staff> element on each note)
    2. Separate parts: Return all parts to support cross-staff notation
       (each note's staff is determined by explicit <staff> element or part default)
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number ("1" or "2")
        
    Returns:
        List of part elements to iterate
    """
    # Always return all parts - we filter by staff at the note level
    # This handles cross-staff notes in both encoding styles
    return list(root.iter("part"))


def _note_belongs_to_staff(note: ET.Element, staff_n: str, 
                           uses_explicit_staves: bool,
                           default_staff: str = UPPER_STAFF) -> bool:
    """
    Check if a note belongs to a specific staff.
    
    Logic:
    1. If note has explicit <staff> element, use that
    2. Otherwise, use the default_staff (based on which part the note is in)
    
    Args:
        note: A <note> element
        staff_n: Staff number to check
        uses_explicit_staves: Whether file uses explicit staves (legacy param, kept for compatibility)
        default_staff: Default staff if note has no explicit <staff> element
        
    Returns:
        True if note belongs to the staff
    """
    # Check for explicit staff element first (works for both encoding styles)
    note_staff = get_note_staff(note)
    if note_staff is not None:
        return note_staff == staff_n
    
    # No explicit staff element - use default for this part
    return default_staff == staff_n


def get_divisions(root: ET.Element) -> int:
    """
    Get the divisions value (duration units per quarter note).
    
    This is essential for converting <duration> values to actual durations.
    
    Args:
        root: The MusicXML root element
        
    Returns:
        Divisions value (defaults to 1 if not found)
    """
    # Check first measure's attributes
    for part in root.iter("part"):
        for measure in part.iter("measure"):
            attrs = measure.find("attributes")
            if attrs is not None:
                div_elem = attrs.find("divisions")
                if div_elem is not None and div_elem.text:
                    return int(div_elem.text.strip())
    return 1  # Default


def parse_musicxml_pitch(note: ET.Element) -> Optional[str]:
    """
    Parse a note's pitch into scientific pitch notation.
    
    MusicXML uses:
    - <step>: A, B, C, D, E, F, G
    - <alter>: -2, -1, 0, 1, 2 for double-flat to double-sharp
    - <octave>: Octave number (4 = middle C octave)
    
    Args:
        note: A <note> element
        
    Returns:
        Pitch string (e.g., "C4", "F#5", "Bb3"), or None if no pitch (rest)
    """
    pitch_elem = note.find("pitch")
    if pitch_elem is None:
        return None
    
    step = pitch_elem.find("step")
    octave = pitch_elem.find("octave")
    alter = pitch_elem.find("alter")
    
    if step is None or octave is None:
        return None
    
    pitch_letter = step.text.strip().upper()
    octave_num = octave.text.strip()
    
    # Handle accidentals
    accidental = ""
    if alter is not None and alter.text:
        alter_val = int(float(alter.text.strip()))
        accidental = ALTER_TO_SYMBOL.get(alter_val, "")
    
    return f"{pitch_letter}{accidental}{octave_num}"


def get_note_type_duration(note: ET.Element) -> Optional[float]:
    """
    Get the visual/notated duration from the <type> element.
    
    This is the duration based on the note symbol (quarter, eighth, etc.)
    before any tuplet modification. Different from parse_musicxml_duration()
    which uses the actual <duration> element.
    
    Use cases:
    - Fallback when <duration> is missing
    - Comparing notated vs actual duration (e.g., tuplets)
    - Display/debugging purposes
    - Future extensions for notation analysis
    
    Args:
        note: A <note> element
        
    Returns:
        Base duration in quarter notes (with dots applied), or None if not found
    
    Note:
        This does NOT apply tuplet time-modification. For actual sounding
        duration, use parse_musicxml_duration() instead.
    """
    type_elem = note.find("type")
    if type_elem is None or not type_elem.text:
        return None
    
    note_type = type_elem.text.strip()
    base_duration = DURATION_TYPE_MAP.get(note_type)
    
    if base_duration is None:
        return None
    
    # Apply dots (each dot adds half of the previous value)
    dot_count = len(note.findall("dot"))
    duration = base_duration
    dot_value = base_duration / 2
    for _ in range(dot_count):
        duration += dot_value
        dot_value /= 2
    
    return duration


def parse_musicxml_duration(note: ET.Element, divisions: int) -> Optional[float]:
    """
    Parse a note's duration in quarter notes.
    
    Uses the <duration> element and converts using divisions.
    Falls back to get_note_type_duration() if <duration> is missing.
    Grace notes return None (they have no duration).
    
    Args:
        note: A <note> element
        divisions: The divisions value for this score
        
    Returns:
        Duration in quarter notes, or None for grace notes
    """
    # Grace notes have no duration
    if is_grace_note(note):
        return None
    
    duration_elem = note.find("duration")
    if duration_elem is not None and duration_elem.text:
        duration_val = int(duration_elem.text.strip())
        # Convert to quarter notes: duration_val / divisions = quarter notes
        return duration_val / divisions
    
    # Fallback: try to get duration from <type> element
    # This handles cases where <duration> is missing but <type> is present
    type_duration = get_note_type_duration(note)
    if type_duration is not None:
        return type_duration
    
    return None


# ============================================================================
# TIE HANDLING
# ============================================================================

def _get_tied_note_info(root: ET.Element, staff_n: str) -> Tuple[Set[str], Dict[str, str]]:
    """
    Analyze tie relationships in a staff.
    
    Returns two structures:
    1. Set of note IDs that are tie continuations (should not be counted separately)
    2. Dict mapping tie start note IDs to their continuation note IDs
    
    MusicXML ties are indicated by:
    - <tie type="start"/> - this note starts a tie
    - <tie type="stop"/> - this note is the end of a tie
    - A note can have both (middle of a tie chain)
    
    We need to track ties by matching pitch, staff, voice, and sequential position.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number to analyze
        
    Returns:
        Tuple of (tied_continuation_positions, tie_chain_map)
    """
    # MusicXML ties are positional - we need to track by:
    # (pitch, staff, voice) and then match start to stop sequentially
    
    tie_starts: Dict[Tuple[str, str, str], List[Tuple[int, int, ET.Element]]] = defaultdict(list)
    tie_stops: Dict[Tuple[str, str, str], List[Tuple[int, int, ET.Element]]] = defaultdict(list)
    
    divisions = get_divisions(root)
    uses_explicit = _uses_explicit_staves(root)
    parts_to_iterate = _get_parts_for_staff(root, staff_n)
    
    for part in parts_to_iterate:
        default_staff = _get_default_staff_for_part(root, part)
        measure_idx = 0
        for measure in part.iter("measure"):
            position = 0  # Position in divisions from measure start
            chord_position = 0  # Position of the current chord's first note
            
            for elem in measure:
                if elem.tag == "note":
                    note = elem
                    
                    # Determine the effective position for this note
                    # Chord notes share position with their parent non-chord note
                    if is_chord_note(note):
                        note_position = chord_position
                    else:
                        note_position = position
                        chord_position = position  # Save for potential chord notes
                    
                    # Skip if not on target staff
                    if not _note_belongs_to_staff(note, staff_n, uses_explicit, default_staff):
                        # Still need to track position for non-chord notes
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position += int(dur_elem.text.strip())
                        continue
                    
                    # Skip invisible notes
                    if not is_visible(note):
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position += int(dur_elem.text.strip())
                        continue
                    
                    # Skip rests
                    if is_rest(note):
                        if not is_chord_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position += int(dur_elem.text.strip())
                        continue
                    
                    pitch = parse_musicxml_pitch(note)
                    if pitch is None:
                        continue
                    
                    voice = get_note_voice(note)
                    key = (pitch, staff_n, voice)
                    
                    # Check for tie start/stop - use note_position for chords
                    for tie in note.findall("tie"):
                        tie_type = tie.get("type")
                        if tie_type == "start":
                            tie_starts[key].append((measure_idx, note_position, note))
                        elif tie_type == "stop":
                            tie_stops[key].append((measure_idx, note_position, note))
                    
                    # Update position for non-chord notes
                    if not is_chord_note(note) and not is_grace_note(note):
                        dur_elem = note.find("duration")
                        if dur_elem is not None and dur_elem.text:
                            position += int(dur_elem.text.strip())
                
                elif elem.tag == "backup":
                    dur_elem = elem.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        position -= int(dur_elem.text.strip())
                
                elif elem.tag == "forward":
                    dur_elem = elem.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        position += int(dur_elem.text.strip())
            
            measure_idx += 1
    
    # Match tie starts to stops
    # A tie stop matches the first unmatched tie start for the same pitch/voice
    tied_continuations: Set[Tuple[int, int, str]] = set()  # (measure_idx, position, pitch) of continuation notes
    
    for key, stops in tie_stops.items():
        pitch = key[0]  # Extract pitch from the key (pitch, staff, voice)
        starts = tie_starts.get(key, [])
        start_idx = 0
        
        for stop_measure, stop_pos, stop_note in sorted(stops):
            # Find the matching start (must be before this stop)
            while start_idx < len(starts):
                start_measure, start_pos, start_note = starts[start_idx]
                if (start_measure, start_pos) < (stop_measure, stop_pos):
                    # This is the matching start
                    tied_continuations.add((stop_measure, stop_pos, pitch))
                    start_idx += 1
                    break
                start_idx += 1
    
    return tied_continuations


def _build_tie_duration_map(root: ET.Element, staff_n: str, divisions: int) -> Dict[Tuple[int, int, str], float]:
    """
    Build a map of tie-adjusted durations for tied note chains.
    
    For a tied note chain (e.g., half tied to quarter), the first note
    should report the total duration (3 quarter notes), and subsequent
    notes should not be counted.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number to analyze
        divisions: Divisions value for duration calculation
        
    Returns:
        Dict mapping (measure_idx, position, pitch) to total tied duration
    """
    # First pass: collect all notes with ties and their durations
    notes_info: List[Tuple[int, int, str, str, float, bool, bool]] = []  # (measure, pos, pitch, voice, dur, is_start, is_stop)
    
    uses_explicit = _uses_explicit_staves(root)
    parts_to_iterate = _get_parts_for_staff(root, staff_n)
    
    for part in parts_to_iterate:
        default_staff = _get_default_staff_for_part(root, part)
        measure_idx = 0
        for measure in part.iter("measure"):
            position = 0
            chord_position = 0  # Track position for chord notes
            
            for elem in measure:
                if elem.tag == "note":
                    note = elem
                    
                    # Determine effective position for this note
                    if is_chord_note(note):
                        note_position = chord_position
                    else:
                        note_position = position
                        chord_position = position
                    
                    if not _note_belongs_to_staff(note, staff_n, uses_explicit, default_staff):
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position += int(dur_elem.text.strip())
                        continue
                    
                    if not is_visible(note) or is_rest(note):
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position += int(dur_elem.text.strip())
                        continue
                    
                    pitch = parse_musicxml_pitch(note)
                    if pitch is None:
                        continue
                    
                    voice = get_note_voice(note)
                    duration = parse_musicxml_duration(note, divisions) or 0.0
                    
                    is_tie_start = any(t.get("type") == "start" for t in note.findall("tie"))
                    is_tie_stop = any(t.get("type") == "stop" for t in note.findall("tie"))
                    
                    notes_info.append((measure_idx, note_position, pitch, voice, duration, is_tie_start, is_tie_stop))
                    
                    if not is_chord_note(note) and not is_grace_note(note):
                        dur_elem = note.find("duration")
                        if dur_elem is not None and dur_elem.text:
                            position += int(dur_elem.text.strip())
                
                elif elem.tag == "backup":
                    dur_elem = elem.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        position -= int(dur_elem.text.strip())
                
                elif elem.tag == "forward":
                    dur_elem = elem.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        position += int(dur_elem.text.strip())
            
            measure_idx += 1
    
    # Build tie chains and calculate total durations
    tie_durations: Dict[Tuple[int, int, str], float] = {}
    
    # Group by (pitch, voice) and sort by position
    by_pitch_voice: Dict[Tuple[str, str], List[Tuple[int, int, float, bool, bool]]] = defaultdict(list)
    for measure, pos, pitch, voice, dur, is_start, is_stop in notes_info:
        by_pitch_voice[(pitch, voice)].append((measure, pos, dur, is_start, is_stop))
    
    for (pitch, voice), notes in by_pitch_voice.items():
        notes.sort()  # Sort by (measure, position)
        
        chain_start = None
        chain_duration = 0.0
        
        for measure, pos, dur, is_start, is_stop in notes:
            if is_stop and chain_start is not None:
                # End of chain - add duration
                chain_duration += dur
                # Store total duration for the chain start
                tie_durations[(chain_start[0], chain_start[1], pitch)] = chain_duration
                
                if is_start:
                    # This note is also a start (middle of longer chain continues)
                    chain_start = (measure, pos)
                    chain_duration = dur
                else:
                    # Chain ends here
                    chain_start = None
                    chain_duration = 0.0
            elif is_start:
                # Start of a new chain
                chain_start = (measure, pos)
                chain_duration = dur
    
    return tie_durations


# ============================================================================
# NOTE COLLECTION
# ============================================================================

def get_notes_in_staff(root: ET.Element, staff_n: str,
                       include_grace: bool = True,
                       exclude_tied_continuations: bool = True) -> List[ET.Element]:
    """
    Get all note elements in a staff.
    
    Handles two MusicXML encoding styles:
    1. Single part with <staves>2</staves> and <staff> elements on notes
    2. Separate parts (P1 for upper, P2 for lower) without <staff> elements
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number ("1" for upper, "2" for lower)
        include_grace: Whether to include grace notes
        exclude_tied_continuations: Whether to exclude tied continuation notes
        
    Returns:
        List of <note> elements
    """
    notes = []
    tied_continuations = set()
    
    if exclude_tied_continuations:
        tied_continuations = _get_tied_note_info(root, staff_n)
    
    uses_explicit = _uses_explicit_staves(root)
    parts_to_iterate = _get_parts_for_staff(root, staff_n)
    
    for part in parts_to_iterate:
        default_staff = _get_default_staff_for_part(root, part)
        measure_idx = 0
        for measure in part.iter("measure"):
            position = 0
            chord_position = 0  # Track position for chord notes
            
            for elem in measure:
                if elem.tag == "note":
                    note = elem
                    
                    # Determine effective position for this note
                    if is_chord_note(note):
                        note_position = chord_position
                    else:
                        note_position = position
                        chord_position = position
                    
                    # Check staff
                    if not _note_belongs_to_staff(note, staff_n, uses_explicit, default_staff):
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position += int(dur_elem.text.strip())
                        continue
                    
                    # Skip invisible notes
                    if not is_visible(note):
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position += int(dur_elem.text.strip())
                        continue
                    
                    # Skip rests
                    if is_rest(note):
                        if not is_chord_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position += int(dur_elem.text.strip())
                        continue
                    
                    # Skip grace notes if not including them
                    if not include_grace and is_grace_note(note):
                        continue
                    
                    # Skip tied continuations - use note_position for chord notes
                    # Must match both position AND pitch
                    if exclude_tied_continuations:
                        pitch = parse_musicxml_pitch(note)
                        if pitch and (measure_idx, note_position, pitch) in tied_continuations:
                            if not is_chord_note(note) and not is_grace_note(note):
                                dur_elem = note.find("duration")
                                if dur_elem is not None and dur_elem.text:
                                    position += int(dur_elem.text.strip())
                            continue
                    
                    notes.append(note)
                    
                    # Update position
                    if not is_chord_note(note) and not is_grace_note(note):
                        dur_elem = note.find("duration")
                        if dur_elem is not None and dur_elem.text:
                            position += int(dur_elem.text.strip())
                
                elif elem.tag == "backup":
                    dur_elem = elem.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        position -= int(dur_elem.text.strip())
                
                elif elem.tag == "forward":
                    dur_elem = elem.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        position += int(dur_elem.text.strip())
            
            measure_idx += 1
    
    return notes


def get_rests_in_staff(root: ET.Element, staff_n: str,
                       include_invisible: bool = False) -> List[ET.Element]:
    """
    Get all rest elements in a staff.
    
    Handles two MusicXML encoding styles:
    1. Single part with <staves>2</staves> and <staff> elements on notes
    2. Separate parts (P1 for upper, P2 for lower) without <staff> elements
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number ("1" for upper, "2" for lower)
        include_invisible: Whether to include invisible rests
        
    Returns:
        List of <note> elements that are rests
    """
    rests = []
    
    uses_explicit = _uses_explicit_staves(root)
    parts_to_iterate = _get_parts_for_staff(root, staff_n)
    
    for part in parts_to_iterate:
        default_staff = _get_default_staff_for_part(root, part)
        for measure in part.iter("measure"):
            for note in measure.iter("note"):
                # Check if it's a rest
                if not is_rest(note):
                    continue
                
                # Check staff
                if not _note_belongs_to_staff(note, staff_n, uses_explicit, default_staff):
                    continue
                
                # Check visibility
                if not include_invisible and not is_visible(note):
                    continue
                
                rests.append(note)
    
    return rests


def count_notes_in_staff(root: ET.Element, staff_n: str,
                         include_grace: bool = True) -> int:
    """
    Count notes in a staff.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes
        
    Returns:
        Count of notes
    """
    notes = get_notes_in_staff(root, staff_n, include_grace=include_grace,
                               exclude_tied_continuations=True)
    return len(notes)


def count_rests_in_staff(root: ET.Element, staff_n: str) -> int:
    """
    Count visible rests in a staff.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        
    Returns:
        Count of rests
    """
    rests = get_rests_in_staff(root, staff_n, include_invisible=False)
    return len(rests)


# ============================================================================
# PITCH FUNCTIONS
# ============================================================================

def _get_all_pitches_in_staff(root: ET.Element, staff_n: str,
                              include_grace: bool = True) -> List[str]:
    """
    Get all pitches from a staff as scientific pitch strings.
    
    Internal helper used by get_pitch_classes_in_staff and get_lowest_pitch_in_staff.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes
        
    Returns:
        List of pitches in scientific notation
    """
    notes = get_notes_in_staff(root, staff_n, include_grace=include_grace,
                               exclude_tied_continuations=True)
    pitches = []
    
    for note in notes:
        pitch = parse_musicxml_pitch(note)
        if pitch:
            pitches.append(pitch)
    
    return pitches


def get_pitch_classes_in_staff(root: ET.Element, staff_n: str,
                               include_grace: bool = True) -> Set[str]:
    """
    Get all unique pitch classes in a staff (ignoring octave).
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes
        
    Returns:
        Set of pitch class names (e.g., {"C", "D", "F#", "Bb"})
    """
    import re
    
    pitches = _get_all_pitches_in_staff(root, staff_n, include_grace)
    pitch_classes = set()
    
    for pitch in pitches:
        # Extract pitch class (everything except the octave number)
        match = re.match(r'([A-G][#b]*)', pitch)
        if match:
            pitch_classes.add(match.group(1))
    
    return pitch_classes


def get_lowest_pitch_in_staff(root: ET.Element, staff_n: str,
                              include_grace: bool = True) -> Optional[str]:
    """
    Find the lowest pitch in a staff.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes
        
    Returns:
        The lowest pitch in scientific notation, or None if no notes
    """
    pitches = _get_all_pitches_in_staff(root, staff_n, include_grace)
    
    if not pitches:
        return None
    
    lowest_midi = float('inf')
    lowest_pitch = None
    
    for pitch in pitches:
        midi = pitch_to_midi(pitch)
        if midi < lowest_midi:
            lowest_midi = midi
            lowest_pitch = pitch
    
    return lowest_pitch


# ============================================================================
# TIMING AND FIRST/LAST NOTE FUNCTIONS
# ============================================================================

def _collect_notes_with_timing(root: ET.Element, staff_n: str,
                               include_grace: bool = True,
                               return_highest_in_chord: bool = True) -> List[Tuple[Tuple[int, float, int], ET.Element]]:
    """
    Collect notes with their timing information for sorting.
    
    Each note gets a timing tuple: (measure_index, position, doc_order)
    - measure_index: 0-based measure number
    - position: Position in divisions from measure start (float to handle grace notes)
    - doc_order: Document order within the same position (for stable sorting)
    
    When return_highest_in_chord is True, for chord notes at the same position,
    only the highest pitch is returned.
    
    Handles two MusicXML encoding styles:
    1. Single part with <staves>2</staves> and <staff> elements on notes
    2. Separate parts (P1 for upper, P2 for lower) without <staff> elements
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes
        return_highest_in_chord: Whether to return only highest pitch per chord
        
    Returns:
        List of ((measure_idx, position, doc_order), note) tuples, sorted by timing
    """
    divisions = get_divisions(root)
    tied_continuations = _get_tied_note_info(root, staff_n)
    
    uses_explicit = _uses_explicit_staves(root)
    parts_to_iterate = _get_parts_for_staff(root, staff_n)
    
    # Collect all notes with timing info
    raw_notes: List[Tuple[int, float, int, ET.Element]] = []  # (measure, position, doc_order, note)
    
    for part in parts_to_iterate:
        default_staff = _get_default_staff_for_part(root, part)
        # Cross-staff notes (from a different part's staff) get an offset in doc_order
        # so they sort after "native" notes at the same position
        is_cross_staff_part = (default_staff != staff_n)
        doc_order_base = CROSS_STAFF_POSITION_OFFSET if is_cross_staff_part else 0
        
        measure_idx = 0
        for measure in part.iter("measure"):
            position = 0.0
            doc_order = doc_order_base
            grace_offset = 0  # Counter for grace notes at same position
            last_regular_position = 0.0
            
            for elem in measure:
                if elem.tag == "note":
                    note = elem
                    
                    # Check staff
                    if not _note_belongs_to_staff(note, staff_n, uses_explicit, default_staff):
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position = float(int(dur_elem.text.strip())) + last_regular_position
                                last_regular_position = position
                                grace_offset = 0
                        continue
                    
                    # Skip invisible
                    if not is_visible(note):
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position = float(int(dur_elem.text.strip())) + last_regular_position
                                last_regular_position = position
                                grace_offset = 0
                        continue
                    
                    # Skip rests
                    if is_rest(note):
                        if not is_chord_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position = float(int(dur_elem.text.strip())) + last_regular_position
                                last_regular_position = position
                                grace_offset = 0
                        continue
                    
                    # Skip tied continuations - must match position AND pitch
                    int_position = int(last_regular_position) if not is_chord_note(note) else int(position)
                    pitch = parse_musicxml_pitch(note)
                    if pitch and (measure_idx, int_position, pitch) in tied_continuations:
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                position = float(int(dur_elem.text.strip())) + last_regular_position
                                last_regular_position = position
                                grace_offset = 0
                        continue
                    
                    # Handle grace notes
                    if is_grace_note(note):
                        if not include_grace:
                            continue
                        # Grace notes get position just before the next regular note
                        # Use negative offset from current position
                        effective_position = last_regular_position - (1.0 - grace_offset * GRACE_NOTE_POSITION_INCREMENT)
                        grace_offset += 1
                        raw_notes.append((measure_idx, effective_position, doc_order, note))
                        doc_order += 1
                        continue
                    
                    # Handle chord notes (same position as previous note)
                    # Chord notes share position with the previous non-chord note
                    if is_chord_note(note):
                        # Use the position of the previous non-chord note (before it updated position)
                        chord_position = last_regular_position
                        # Look back to find what position that note was at
                        # We need to subtract the duration that was just added
                        if raw_notes:
                            # Get the position from the most recent note in this measure
                            for prev_m, prev_p, prev_d, prev_n in reversed(raw_notes):
                                if prev_m == measure_idx:
                                    chord_position = prev_p
                                    break
                        raw_notes.append((measure_idx, chord_position, doc_order, note))
                        doc_order += 1
                        continue
                    
                    # Regular note
                    raw_notes.append((measure_idx, last_regular_position, doc_order, note))
                    doc_order += 1
                    
                    # Update position
                    dur_elem = note.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        last_regular_position += float(int(dur_elem.text.strip()))
                        grace_offset = 0
                
                elif elem.tag == "backup":
                    dur_elem = elem.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        last_regular_position -= float(int(dur_elem.text.strip()))
                        if last_regular_position < 0:
                            last_regular_position = 0.0
                        grace_offset = 0
                
                elif elem.tag == "forward":
                    dur_elem = elem.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        last_regular_position += float(int(dur_elem.text.strip()))
                        grace_offset = 0
            
            measure_idx += 1
    
    if not raw_notes:
        return []
    
    # Sort by timing
    raw_notes.sort(key=lambda x: (x[0], x[1], x[2]))
    
    if not return_highest_in_chord:
        return [((m, p, d), n) for m, p, d, n in raw_notes]
    
    # Group by (measure, position) and return highest pitch per group
    result: List[Tuple[Tuple[int, float, int], ET.Element]] = []
    
    current_group: List[Tuple[int, float, int, ET.Element]] = []
    current_key = None
    
    for m, p, d, n in raw_notes:
        key = (m, int(p))  # Group by measure and integer position
        
        if key != current_key:
            # Process previous group
            if current_group:
                # Find highest pitch
                highest = None
                highest_midi = float('-inf')
                highest_timing = None
                for gm, gp, gd, gn in current_group:
                    pitch = parse_musicxml_pitch(gn)
                    if pitch:
                        midi = pitch_to_midi(pitch)
                        if midi > highest_midi:
                            highest_midi = midi
                            highest = gn
                            highest_timing = (gm, gp, gd)
                if highest is not None:
                    result.append((highest_timing, highest))
            
            current_group = [(m, p, d, n)]
            current_key = key
        else:
            current_group.append((m, p, d, n))
    
    # Don't forget last group
    if current_group:
        highest = None
        highest_midi = float('-inf')
        highest_timing = None
        for gm, gp, gd, gn in current_group:
            pitch = parse_musicxml_pitch(gn)
            if pitch:
                midi = pitch_to_midi(pitch)
                if midi > highest_midi:
                    highest_midi = midi
                    highest = gn
                    highest_timing = (gm, gp, gd)
        if highest is not None:
            result.append((highest_timing, highest))
    
    return result


def get_first_note_in_staff(root: ET.Element, staff_n: str,
                            include_grace: bool = True,
                            return_highest_in_chord: bool = True) -> Optional[ET.Element]:
    """
    Get the first note in a staff (by temporal position).
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes
        return_highest_in_chord: If multiple notes at same time, return highest pitch
        
    Returns:
        The first note element, or None if no notes
    """
    notes = _collect_notes_with_timing(root, staff_n, include_grace, return_highest_in_chord)
    if not notes:
        return None
    return notes[0][1]


def get_last_note_in_staff(root: ET.Element, staff_n: str,
                           include_grace: bool = True,
                           return_highest_in_chord: bool = True) -> Optional[ET.Element]:
    """
    Get the last note in a staff (by temporal position).
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes
        return_highest_in_chord: If multiple notes at same time, return highest pitch
        
    Returns:
        The last note element, or None if no notes
    """
    notes = _collect_notes_with_timing(root, staff_n, include_grace, return_highest_in_chord)
    if not notes:
        return None
    return notes[-1][1]


def get_first_note_pitch(root: ET.Element, staff_n: str,
                         include_grace: bool = True) -> Optional[str]:
    """
    Get the pitch of the first note in a staff.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes
        
    Returns:
        Pitch in scientific notation, or None if no notes
    """
    note = get_first_note_in_staff(root, staff_n, include_grace, return_highest_in_chord=True)
    if note is None:
        return None
    return parse_musicxml_pitch(note)


def get_first_note_duration(root: ET.Element, staff_n: str,
                            include_grace: bool = True) -> Optional[float]:
    """
    Get the duration of the first note in a staff.
    
    Includes tie chain duration if the note is tied.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes (grace notes return None duration)
        
    Returns:
        Duration in quarter notes, or None if no notes
    """
    divisions = get_divisions(root)
    
    # Get notes with timing to find the first
    notes = _collect_notes_with_timing(root, staff_n, include_grace, return_highest_in_chord=True)
    if not notes:
        return None
    
    timing, first_note = notes[0]
    
    # Grace notes have no duration
    if is_grace_note(first_note):
        return None
    
    # Get base duration
    duration = parse_musicxml_duration(first_note, divisions)
    if duration is None:
        return None
    
    # Check for tie and add continuation durations
    has_tie_start = any(t.get("type") == "start" for t in first_note.findall("tie"))
    
    if has_tie_start:
        pitch = parse_musicxml_pitch(first_note)
        if pitch:
            tie_durations = _build_tie_duration_map(root, staff_n, divisions)
            measure_idx, position, _ = timing
            key = (measure_idx, int(position), pitch)
            if key in tie_durations:
                duration = tie_durations[key]
    
    return duration


# ============================================================================
# DURATION FUNCTIONS
# ============================================================================

def get_all_note_durations_in_staff(root: ET.Element, staff_n: str,
                                    include_grace: bool = False,
                                    sum_ties: bool = True) -> List[float]:
    """
    Get all note durations in a staff.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes (they have 0 duration)
        sum_ties: Whether to sum durations across tied notes
        
    Returns:
        List of durations in quarter notes
    """
    divisions = get_divisions(root)
    durations = []
    
    tied_continuations = _get_tied_note_info(root, staff_n) if sum_ties else set()
    tie_durations = _build_tie_duration_map(root, staff_n, divisions) if sum_ties else {}
    
    uses_explicit = _uses_explicit_staves(root)
    parts_to_iterate = _get_parts_for_staff(root, staff_n)
    
    for part in parts_to_iterate:
        default_staff = _get_default_staff_for_part(root, part)
        measure_idx = 0
        for measure in part.iter("measure"):
            position = 0
            chord_position = 0  # Position for chord notes
            
            for elem in measure:
                if elem.tag == "note":
                    note = elem
                    
                    # Determine position for this note
                    if is_chord_note(note):
                        note_position = chord_position
                    else:
                        note_position = position
                    
                    if not _note_belongs_to_staff(note, staff_n, uses_explicit, default_staff):
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                chord_position = position
                                position += int(dur_elem.text.strip())
                        continue
                    
                    if not is_visible(note):
                        if not is_chord_note(note) and not is_grace_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                chord_position = position
                                position += int(dur_elem.text.strip())
                        continue
                    
                    if is_rest(note):
                        if not is_chord_note(note):
                            dur_elem = note.find("duration")
                            if dur_elem is not None and dur_elem.text:
                                chord_position = position
                                position += int(dur_elem.text.strip())
                        continue
                    
                    # Skip tied continuations - must match position AND pitch
                    if sum_ties:
                        pitch = parse_musicxml_pitch(note)
                        if pitch and (measure_idx, note_position, pitch) in tied_continuations:
                            if not is_chord_note(note) and not is_grace_note(note):
                                dur_elem = note.find("duration")
                                if dur_elem is not None and dur_elem.text:
                                    chord_position = position
                                    position += int(dur_elem.text.strip())
                            continue
                    
                    # Skip grace notes unless including them
                    if is_grace_note(note):
                        if include_grace:
                            durations.append(0.0)
                        continue
                    
                    # Get duration
                    duration = parse_musicxml_duration(note, divisions)
                    if duration is None:
                        continue
                    
                    # Check for tie start and use summed duration
                    if sum_ties:
                        has_tie_start = any(t.get("type") == "start" for t in note.findall("tie"))
                        if has_tie_start:
                            pitch = parse_musicxml_pitch(note)
                            if pitch:
                                key = (measure_idx, note_position, pitch)
                                if key in tie_durations:
                                    duration = tie_durations[key]
                    
                    durations.append(duration)
                    
                    if not is_chord_note(note):
                        dur_elem = note.find("duration")
                        if dur_elem is not None and dur_elem.text:
                            chord_position = position
                            position += int(dur_elem.text.strip())
                
                elif elem.tag == "backup":
                    dur_elem = elem.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        position -= int(dur_elem.text.strip())
                        chord_position = position
                
                elif elem.tag == "forward":
                    dur_elem = elem.find("duration")
                    if dur_elem is not None and dur_elem.text:
                        chord_position = position
                        position += int(dur_elem.text.strip())
            
            measure_idx += 1
    
    return durations


def get_longest_duration_in_staff(root: ET.Element, staff_n: str,
                                  sum_ties: bool = True) -> Optional[float]:
    """
    Find the longest note duration in a staff.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        sum_ties: Whether to sum durations across tied notes
        
    Returns:
        The longest duration in quarter notes, or None if no notes
    """
    durations = get_all_note_durations_in_staff(root, staff_n, include_grace=False, sum_ties=sum_ties)
    
    if not durations:
        return None
    
    return max(durations)


def get_interval_first_last(root: ET.Element, staff_n: str,
                            include_grace: bool = True) -> Optional[int]:
    """
    Calculate the interval between first and last notes in a staff.
    
    Args:
        root: The MusicXML root element
        staff_n: Staff number
        include_grace: Whether to include grace notes
        
    Returns:
        Interval in semitones (absolute value), or None if fewer than 2 unique notes
    """
    first_note = get_first_note_in_staff(root, staff_n, include_grace, return_highest_in_chord=True)
    last_note = get_last_note_in_staff(root, staff_n, include_grace, return_highest_in_chord=True)
    
    if first_note is None or last_note is None:
        return None
    
    first_pitch = parse_musicxml_pitch(first_note)
    last_pitch = parse_musicxml_pitch(last_note)
    
    if first_pitch is None or last_pitch is None:
        return None
    
    return calculate_interval_semitones(first_pitch, last_pitch)


# ============================================================================
# CONVENIENCE FUNCTIONS (file path based)
# ============================================================================

def count_lower_staff_notes(file_path: str, **kwargs) -> int:
    """Count notes in the lower staff (staff 2)."""
    root = parse_musicxml_file(file_path)
    return count_notes_in_staff(root, LOWER_STAFF, **kwargs)


def count_upper_staff_notes(file_path: str, **kwargs) -> int:
    """Count notes in the upper staff (staff 1)."""
    root = parse_musicxml_file(file_path)
    return count_notes_in_staff(root, UPPER_STAFF, **kwargs)

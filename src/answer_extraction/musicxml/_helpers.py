"""
MusicXML Helper Functions

Shared utilities for parsing and extracting data from MusicXML files.

Functions:
    Parsing:
        - parse_musicxml: Parse MusicXML file and return root element
        - get_divisions: Extract divisions value for duration calculation
    
    Note Filtering:
        - get_notes_in_range: Get notes within measure range, optionally by staff
        - is_rest: Check if note is a rest
        - is_grace_note: Check if note is a grace note
        - is_invisible_note: Check if note is invisible (formatting)
        - is_tied_continuation: Check if note continues a tie (shouldn't be counted)
    
    Pitch Operations:
        - get_pitch: Extract pitch as 'C#5' or 'Bb3' format
        - pitch_to_midi: Convert pitch string to MIDI number for comparison
        - get_pitch_class: Extract pitch class (note name without octave)
    
    Duration Operations:
        - get_duration_in_beats: Convert duration to beats
        - duration_to_note_name: Convert beats to note name (e.g., 'Dotted eighth note')
        - format_beats: Format beats as integer string if whole number, else decimal
"""

import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional
import re


# ==================== PARSING ====================

def parse_musicxml(file_path: str) -> ET.Element:
    """
    Parse MusicXML file and return root element.
    
    Args:
        file_path: Path to MusicXML file (.xml or .musicxml)
    
    Returns:
        Root element of parsed XML tree
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ET.ParseError: If XML is malformed
    """
    tree = ET.parse(file_path)
    return tree.getroot()


def get_divisions(measure: ET.Element) -> int:
    """
    Get divisions value from measure for duration calculation.
    
    Divisions represents how many time units equal a quarter note.
    For example, divisions=4 means quarter note = 4 units.
    
    Args:
        measure: Measure XML element
    
    Returns:
        Divisions value (defaults to 1 if not found)
    """
    divisions = measure.find('.//divisions')
    return int(divisions.text) if divisions is not None else 1


# ==================== NOTE FILTERING ====================

def get_notes_in_range(
    root: ET.Element, 
    start_measure: int, 
    end_measure: int, 
    staff: Optional[int] = None
) -> List[ET.Element]:
    """
    Get all notes within measure range, optionally filtered by staff.
    
    Args:
        root: Root element of MusicXML document
        start_measure: Starting measure number (inclusive)
        end_measure: Ending measure number (inclusive)
        staff: Optional staff number (1=upper, 2=lower). None = all staves
    
    Returns:
        List of note elements in chronological order
    """
    notes = []
    
    # Iterate through all parts and measures
    for part in root.findall('.//part'):
        for measure in part.findall('.//measure'):
            measure_num = int(measure.get('number', 0))
            
            # Check if measure is in range
            if start_measure <= measure_num <= end_measure:
                # Get divisions for this measure (needed for context)
                divisions = get_divisions(measure)
                
                for note in measure.findall('.//note'):
                    # Filter by staff if specified
                    if staff is not None:
                        note_staff = note.find('staff')
                        if note_staff is None or int(note_staff.text) != staff:
                            continue
                    
                    # Attach measure context to note for later use
                    note.set('_measure_number', str(measure_num))
                    note.set('_divisions', str(divisions))
                    notes.append(note)
    
    return notes


def is_rest(note: ET.Element) -> bool:
    """
    Check if note element is a rest.
    
    Args:
        note: Note XML element
    
    Returns:
        True if note is a rest, False otherwise
    """
    return note.find('rest') is not None


def is_grace_note(note: ET.Element) -> bool:
    """
    Check if note is a grace note (ornamental, no rhythmic value).
    
    Args:
        note: Note XML element
    
    Returns:
        True if note is a grace note, False otherwise
    """
    return note.find('grace') is not None


def is_invisible_note(note: ET.Element) -> bool:
    """
    Check if note is invisible (used for formatting/spacing only).
    
    MusicXML uses print-object="no" for notes that shouldn't be displayed.
    These are formatting/layout helpers and should NOT be counted.
    
    Args:
        note: Note XML element
    
    Returns:
        True if note is invisible, False otherwise
    """
    return note.get('print-object') == 'no'


def is_tied_continuation(note: ET.Element) -> bool:
    """
    Check if note is continuation of a tie (shouldn't be counted separately).
    
    A tied continuation has <tied type="stop"/> but NOT <tied type="start"/>.
    We count the first note of a tie but not the continuation notes.
    
    Args:
        note: Note XML element
    
    Returns:
        True if note only continues a tie (stop but no start), False otherwise
    """
    tied_stop = note.find('.//tied[@type="stop"]')
    
    if tied_stop is not None:
        # Check if this also starts a new tie
        tied_start = note.find('.//tied[@type="start"]')
        # Only return True if this is ONLY a stop (not also a start)
        return tied_start is None
    
    return False


# ==================== PITCH OPERATIONS ====================

def get_pitch(note: ET.Element) -> Optional[str]:
    """
    Extract pitch from note as 'C#5' or 'Bb3' format.
    
    Args:
        note: Note XML element
    
    Returns:
        Pitch string (e.g., 'C#5', 'Bb3', 'D4') or None if rest
    """
    pitch_elem = note.find('pitch')
    if pitch_elem is None:
        return None
    
    step = pitch_elem.find('step').text
    octave = pitch_elem.find('octave').text
    alter = pitch_elem.find('alter')
    
    # Handle alterations (sharps/flats)
    if alter is not None:
        alter_val = int(alter.text)
        if alter_val == 1:
            accidental = '#'
        elif alter_val == -1:
            accidental = 'b'
        elif alter_val == 2:
            accidental = '##'
        elif alter_val == -2:
            accidental = 'bb'
        else:
            accidental = ''
    else:
        accidental = ''
    
    return f"{step}{accidental}{octave}"


def pitch_to_midi(pitch: str) -> int:
    """
    Convert pitch string to MIDI number for comparison.
    
    MIDI number system: C4 (middle C) = 60, A4 (440Hz) = 69
    Each semitone = 1 MIDI number
    
    Args:
        pitch: Pitch string (e.g., 'C#5', 'Bb3')
    
    Returns:
        MIDI note number (0-127)
    
    Examples:
        >>> pitch_to_midi('C4')
        60
        >>> pitch_to_midi('C#5')
        73
        >>> pitch_to_midi('Bb3')
        58
    """
    note_map = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    
    # Parse pitch string
    step = pitch[0]
    rest = pitch[1:]
    
    # Extract accidental and octave
    if '#' in rest:
        accidental = rest.count('#')
        octave = int(rest.replace('#', ''))
    elif 'b' in rest:
        accidental = -rest.count('b')
        octave = int(rest.replace('b', ''))
    else:
        accidental = 0
        octave = int(rest)
    
    return (octave + 1) * 12 + note_map[step] + accidental


def get_pitch_class(pitch: str) -> str:
    """
    Extract pitch class (note name without octave).
    
    Args:
        pitch: Pitch string (e.g., 'C#5', 'Bb3')
    
    Returns:
        Pitch class (e.g., 'C#', 'Bb', 'D')
    
    Examples:
        >>> get_pitch_class('C#5')
        'C#'
        >>> get_pitch_class('Bb3')
        'Bb'
        >>> get_pitch_class('D4')
        'D'
    """
    # Remove octave digit(s) from end
    return re.sub(r'\d+$', '', pitch)


# ==================== DURATION OPERATIONS ====================

def get_duration_in_beats(note: ET.Element, divisions: Optional[int] = None) -> float:
    """
    Convert note duration to beats (quarter note = 1 beat).
    
    Args:
        note: Note XML element
        divisions: Optional divisions value. If None, uses value from note context
    
    Returns:
        Duration in beats (e.g., 0.5 for eighth note, 2.0 for half note)
    """
    duration_elem = note.find('duration')
    if duration_elem is None:
        return 0.0
    
    # Get divisions from parameter or note context
    if divisions is None:
        divisions = int(note.get('_divisions', 1))
    
    return float(duration_elem.text) / divisions


def duration_to_note_name(beats: float) -> str:
    """
    Convert beats to note name (e.g., 2.0 -> 'Half note').
    
    Supports single and double dots, up to 32nd notes.
    Handles floating point precision issues by rounding.
    
    Args:
        beats: Duration in beats (quarter note = 1 beat)
    
    Returns:
        Note name (e.g., 'Quarter note', 'Dotted eighth note', 'Double dotted half note')
    
    Examples:
        >>> duration_to_note_name(1.0)
        'Quarter note'
        >>> duration_to_note_name(0.75)
        'Dotted eighth note'
        >>> duration_to_note_name(3.5)
        'Double dotted half note'
    """
    # Comprehensive duration map including double dotted notes
    duration_map = {
        # Whole notes
        4.0: 'Whole note',
        6.0: 'Dotted whole note',
        7.0: 'Double dotted whole note',
        
        # Half notes
        2.0: 'Half note',
        3.0: 'Dotted half note',
        3.5: 'Double dotted half note',
        
        # Quarter notes
        1.0: 'Quarter note',
        1.5: 'Dotted quarter note',
        1.75: 'Double dotted quarter note',
        
        # Eighth notes
        0.5: 'Eighth note',
        0.75: 'Dotted eighth note',
        0.875: 'Double dotted eighth note',
        
        # Sixteenth notes
        0.25: 'Sixteenth note',
        0.375: 'Dotted sixteenth note',
        0.4375: 'Double dotted sixteenth note',
        
        # Thirty-second notes
        0.125: 'Thirty-second note',
        0.1875: 'Dotted thirty-second note',
        0.21875: 'Double dotted thirty-second note',
    }
    
    # Round to reasonable precision to handle floating point errors
    # Use 5 decimal places to distinguish between close values
    rounded = round(beats, 5)
    return duration_map.get(rounded, f"{beats} beats")


def format_beats(beats: float) -> str:
    """
    Format beats as string: integers without decimals, decimals only when needed.
    
    Args:
        beats: Duration in beats
    
    Returns:
        Formatted string (e.g., '2' not '2.0', but '1.5' for dotted notes)
    
    Examples:
        >>> format_beats(2.0)
        '2'
        >>> format_beats(1.5)
        '1.5'
        >>> format_beats(4.0)
        '4'
        >>> format_beats(0.75)
        '0.75'
    """
    # Check if it's a whole number
    if beats == int(beats):
        return str(int(beats))
    else:
        # Return with minimal decimal places
        return str(beats).rstrip('0').rstrip('.')

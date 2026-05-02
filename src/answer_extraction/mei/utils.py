"""
MEI (Music Encoding Initiative) parsing utilities.

Shared functions for parsing MEI XML files, extracting staff content,
counting notes, and handling the various MEI notation constructs.

MEI 5.0 basics (as used in these files):
- Staff elements have @n attribute: n="1" is upper (treble), n="2" is lower (bass)
- Notes use @pname (pitch name: c,d,e,f,g,a,b), @oct (octave number), @dur (duration)
- Accidentals: @accid (explicit in notation), @accid.ges (gestural/implied by key)
- Durations: 'long', 'breve', 'whole', 'half', 'quarter', '8th', '16th', '32nd', '64th'
- Dots: @dots attribute indicates augmentation dots
- Chords: <chord> element containing multiple <note> elements
- Grace notes: @grace attribute ('acc' = acciaccatura, 'unacc' = appoggiatura, 'unknown')
- Ties: <tie> element with @startid and @endid attributes referencing note xml:ids
- Rests: <rest> element with @dur attribute
- Measure rests: <mRest> for whole-measure rests
- Tuplets: <tuplet> element with @num and @numbase attributes
- Visibility: @visible="false" makes elements non-printing (should be excluded)

Namespace:
- MEI namespace: "http://www.music-encoding.org/ns/mei"
- XML namespace for xml:id: "http://www.w3.org/XML/1998/namespace"

FUTURE ENHANCEMENTS for full movement support:
- Repeat handling: <repeatMark> elements, @left/@right on <measure>
- First/second endings: <ending> elements with @n and @type
- Section markers: <section> elements for structure
- Multi-movement: Multiple <mdiv> elements
- DS/DC markers: segno, coda, dal segno, da capo
"""

import xml.etree.ElementTree as ET
from typing import List, Set, Optional, Dict, Tuple

# Import format-agnostic utilities from core
from ..core.pitch import pitch_to_midi, calculate_interval_semitones
from ..core.duration import format_duration

# MEI namespace
MEI_NS = "http://www.music-encoding.org/ns/mei"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"mei": MEI_NS}

# Staff identifiers
UPPER_STAFF = "1"  # Upper staff (typically treble clef)
LOWER_STAFF = "2"  # Lower staff (typically bass clef)

# Timing constants for note ordering
# Cross-staff notes (notes with @staff attr pointing to different staff) sort after
# regular notes at the same timestamp. 10000 is arbitrary but large enough to never
# conflict with real document order values.
CROSS_STAFF_DOC_ORDER_OFFSET = 10000

# Grace notes don't have real timestamps. When multiple grace notes appear before
# a main note, we assign tiny incremental offsets so they sort in document order
# while appearing "before" the main beat.
GRACE_NOTE_TSTAMP_INCREMENT = 0.0001


# Duration values in quarter notes
# MEI uses string names for durations
DURATION_MAP = {
    'maxima': 32.0,     # Maxima (8 whole notes)
    'long': 16.0,       # Longa (4 whole notes)
    'breve': 8.0,       # Breve (2 whole notes)
    'whole': 4.0,       # Whole note
    '1': 4.0,           # Alternative whole note notation
    'half': 2.0,        # Half note
    '2': 2.0,           # Alternative half note notation
    'quarter': 1.0,     # Quarter note
    '4': 1.0,           # Alternative quarter note notation
    '8th': 0.5,         # Eighth note
    '8': 0.5,           # Alternative eighth note notation
    '16th': 0.25,       # Sixteenth note
    '16': 0.25,         # Alternative sixteenth note notation
    '32nd': 0.125,      # 32nd note
    '32': 0.125,        # Alternative 32nd note notation
    '64th': 0.0625,     # 64th note
    '64': 0.0625,       # Alternative 64th note notation
    '128th': 0.03125,   # 128th note
    '128': 0.03125,     # Alternative 128th note notation
    '256th': 0.015625,  # 256th note
    '256': 0.015625,    # Alternative 256th note notation
}


def get_xml_id(element: ET.Element) -> Optional[str]:
    """
    Get the xml:id of an element.

    Args:
        element: The XML element

    Returns:
        The xml:id value, or None if not present
    """
    return element.get(f"{{{XML_NS}}}id")


def _get_rdg_descendant_ids(root: ET.Element) -> Set[int]:
    """Return id()s of every element that is a descendant of any <rdg>.

    MEI <app> apparatus entries contain a <lem> (preferred reading) and one or
    more <rdg> (variant readings). Only <lem> should be extracted; notes and
    rests inside <rdg> are editorial alternatives and would double-count.
    """
    excluded: Set[int] = set()
    for rdg in root.iter(f"{{{MEI_NS}}}rdg"):
        for elem in rdg.iter():
            excluded.add(id(elem))
    return excluded


def is_visible(element: ET.Element) -> bool:
    """
    Check if an element is visible (will be rendered).
    
    Per the system prompt: "Only respond based on elements that will be 
    visually rendered in the score."
    
    Args:
        element: The XML element
        
    Returns:
        True if the element is visible, False otherwise
    """
    visible_attr = element.get("visible")
    # If visible is explicitly "false", the element is invisible
    return visible_attr != "false"


def is_grace_note(element: ET.Element) -> bool:
    """
    Check if a note element is a grace note.
    
    In MEI, grace notes have a @grace attribute with values like:
    - 'acc' = acciaccatura
    - 'unacc' = appoggiatura
    - 'unknown' = unspecified grace type
    
    Per system prompt: "Always consider grace notes and ornaments to be 
    the same as normal notes."
    
    Args:
        element: A note element
        
    Returns:
        True if this is a grace note
    """
    return element.get("grace") is not None


def parse_mei_duration(element: ET.Element, tuplet_ratio: float = 1.0,
                       parent_dur: Optional[str] = None,
                       parent_dots: int = 0,
                       grace_has_duration: bool = False) -> float:
    """
    Parse the duration of a note or rest element in quarter notes.
    
    Handles:
    - Standard duration values (whole, half, quarter, 8th, 16th, etc.)
    - Dots (adds half the value for each dot)
    - Tuplets (modifies duration by tuplet ratio)
    - Grace notes (return 0 by default, or notated value if grace_has_duration=True)
    - Notes in chords (inherit duration from parent chord)
    
    Args:
        element: A note or rest element
        tuplet_ratio: The tuplet modification ratio (e.g., 2/3 for triplets)
        parent_dur: Duration from parent chord element (for notes in chords)
        parent_dots: Dots from parent chord element
        grace_has_duration: If True, return notated duration for grace notes
        
    Returns:
        Duration in quarter notes
    """
    # Grace notes are durationless for duration counting purposes
    # Unless we specifically want their notated value (for Q9)
    if is_grace_note(element) and not grace_has_duration:
        return 0.0
    
    # Get duration - check element first, then use parent (chord) values
    dur_attr = element.get("dur") or parent_dur
    if not dur_attr:
        return 0.0
    
    # Get base duration
    base_duration = DURATION_MAP.get(dur_attr, 1.0)
    
    # Apply dots - check element first, then use parent (chord) value
    dots_str = element.get("dots")
    if dots_str is not None:
        dots = int(dots_str)
    else:
        dots = parent_dots
    
    duration = base_duration
    dot_value = base_duration / 2
    for _ in range(dots):
        duration += dot_value
        dot_value /= 2
    
    # Apply tuplet ratio
    duration *= tuplet_ratio
    
    return duration


def parse_mei_pitch(element: ET.Element) -> Optional[str]:
    """
    Parse the pitch of a note element to scientific notation.
    
    Uses @pname for pitch letter, @oct for octave, and accidentals from:
    - @accid/@accid.ges attributes on the note element
    - Child <accid> element with @accid/@accid.ges attributes (at any nesting level)
    - Nested <app>/<lem>/<accid> structure (editorial apparatus)
    - <supplied><accid></supplied> structure (editorial additions)
    
    Args:
        element: A note element
        
    Returns:
        Pitch in scientific notation (e.g., "C4", "F#5", "Bb3")
    """
    pname = element.get("pname")
    oct_attr = element.get("oct")
    
    if not pname or not oct_attr:
        return None
    
    # Build pitch name
    pitch = pname.upper()
    
    # Check for accidentals (explicit first, then gestural)
    # First check note element attributes
    accid = element.get("accid") or element.get("accid.ges")
    
    # If not found, search for any <accid> element anywhere inside the note
    # This handles <accid>, <supplied><accid>, <app><lem><accid>, etc.
    if not accid:
        for accid_elem in element.iter(f"{{{MEI_NS}}}accid"):
            accid = accid_elem.get("accid") or accid_elem.get("accid.ges")
            if accid:
                break
    
    if accid:
        if accid == 's':
            pitch += '#'
        elif accid == 'ss':
            pitch += '##'
        elif accid == 'f':
            pitch += 'b'
        elif accid == 'ff':
            pitch += 'bb'
        elif accid == 'n':
            pass  # Natural, no modification needed
        # x = double sharp (same as ss)
        elif accid == 'x':
            pitch += '##'
    
    return f"{pitch}{oct_attr}"


def _get_tied_end_note_ids(root: ET.Element) -> Set[str]:
    """
    Find all note IDs that are the end of a tie.
    
    These notes should not be counted separately since they are
    continuations of a tied note.
    
    Args:
        root: The MEI document root element
        
    Returns:
        Set of xml:id values for notes that are tie endpoints
    """
    tied_ends = set()
    rdg_ids = _get_rdg_descendant_ids(root)

    # Find all <tie> elements
    for tie in root.iter(f"{{{MEI_NS}}}tie"):
        if id(tie) in rdg_ids:
            continue
        if not is_visible(tie):
            continue
        endid = tie.get("endid")
        if endid:
            # Remove the leading '#' from the reference
            if endid.startswith("#"):
                endid = endid[1:]
            tied_ends.add(endid)

    return tied_ends


def _get_tied_note_pairs(root: ET.Element) -> List[Tuple[str, str]]:
    """
    Get all tie start/end pairs for duration calculations.
    
    Args:
        root: The MEI document root element
        
    Returns:
        List of (start_id, end_id) tuples
    """
    pairs = []
    rdg_ids = _get_rdg_descendant_ids(root)

    for tie in root.iter(f"{{{MEI_NS}}}tie"):
        if id(tie) in rdg_ids:
            continue
        if not is_visible(tie):
            continue
        startid = tie.get("startid")
        endid = tie.get("endid")
        if startid and endid:
            # Remove leading '#' from references
            if startid.startswith("#"):
                startid = startid[1:]
            if endid.startswith("#"):
                endid = endid[1:]
            pairs.append((startid, endid))

    return pairs


def get_notes_in_staff(root: ET.Element, staff_n: str, 
                       include_grace: bool = True,
                       exclude_tied_ends: bool = False) -> List[ET.Element]:
    """
    Get all note elements from a specific staff.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number (e.g., "1" or "2")
        include_grace: Whether to include grace notes
        exclude_tied_ends: Whether to exclude notes that are tie continuations
        
    Returns:
        List of note elements
    """
    tied_ends = _get_tied_end_note_ids(root) if exclude_tied_ends else set()
    rdg_ids = _get_rdg_descendant_ids(root)
    notes = []

    # Note on @staff: MEI's @staff attribute is a visual override, not an
    # analytical reassignment (per MEI 4.0 guidelines). Counting uses the
    # encoding-parent <staff> element, so that @staff notes stay in the staff
    # where they are encoded. This also matches music21's conversion behavior
    # for most of the corpus.
    for staff in root.iter(f"{{{MEI_NS}}}staff"):
        if staff.get("n") != staff_n:
            continue
        for note in staff.iter(f"{{{MEI_NS}}}note"):
            if id(note) in rdg_ids:
                continue
            if not is_visible(note):
                continue
            if not include_grace and is_grace_note(note):
                continue
            if exclude_tied_ends:
                note_id = get_xml_id(note)
                if note_id and note_id in tied_ends:
                    continue
            notes.append(note)

    return notes


def get_rests_in_staff(root: ET.Element, staff_n: str, 
                       include_measure_rests: bool = True) -> List[ET.Element]:
    """
    Get all visible rest elements from a specific staff.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number (e.g., "1" or "2")
        include_measure_rests: Whether to include mRest elements
        
    Returns:
        List of rest elements (both <rest> and <mRest> if included)
    """
    rests = []
    rdg_ids = _get_rdg_descendant_ids(root)

    # Find all staff elements with the specified n attribute
    for staff in root.iter(f"{{{MEI_NS}}}staff"):
        if staff.get("n") != staff_n:
            continue

        # Get all rests within this staff
        for rest in staff.iter(f"{{{MEI_NS}}}rest"):
            if id(rest) in rdg_ids:
                continue
            if is_visible(rest):
                rests.append(rest)

        # Get measure rests if requested
        if include_measure_rests:
            for mrest in staff.iter(f"{{{MEI_NS}}}mRest"):
                if id(mrest) in rdg_ids:
                    continue
                if is_visible(mrest):
                    rests.append(mrest)

    return rests


def count_notes_in_staff(root: ET.Element, staff_n: str, 
                         include_grace: bool = True) -> int:
    """
    Count notes in a specific staff, excluding tied note continuations.
    
    Per system prompt: "Count tied notes only once" and "Include grace notes"
    
    Args:
        root: The MEI document root element
        staff_n: The staff number to count (e.g., "1" or "2")
        include_grace: Whether to include grace notes
        
    Returns:
        The count of notes
    """
    notes = get_notes_in_staff(root, staff_n, include_grace=include_grace, 
                               exclude_tied_ends=True)
    return len(notes)


def count_rests_in_staff(root: ET.Element, staff_n: str,
                         include_measure_rests: bool = True) -> int:
    """
    Count visible rests in a specific staff.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number to count
        include_measure_rests: Whether to count mRest elements
        
    Returns:
        The count of rests
    """
    rests = get_rests_in_staff(root, staff_n, include_measure_rests)
    return len(rests)


def _get_all_pitches_in_staff(root: ET.Element, staff_n: str,
                              include_grace: bool = True) -> List[str]:
    """
    Get all pitches from a staff as scientific pitch strings.
    
    Internal helper used by get_pitch_classes_in_staff and get_lowest_pitch_in_staff.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number
        include_grace: Whether to include grace notes
        
    Returns:
        List of pitches in scientific notation
    """
    notes = get_notes_in_staff(root, staff_n, include_grace=include_grace)
    pitches = []
    
    for note in notes:
        pitch = parse_mei_pitch(note)
        if pitch:
            pitches.append(pitch)
    
    return pitches


def get_pitch_classes_in_staff(root: ET.Element, staff_n: str,
                               include_grace: bool = True) -> Set[str]:
    """
    Get all unique pitch classes in a staff (ignoring octave).
    
    Args:
        root: The MEI document root element
        staff_n: The staff number
        include_grace: Whether to include grace notes
        
    Returns:
        Set of pitch class names (e.g., {"C", "D", "F#", "Bb"})
    """
    pitches = _get_all_pitches_in_staff(root, staff_n, include_grace)
    pitch_classes = set()
    
    for pitch in pitches:
        # Extract pitch class (everything except the octave number)
        import re
        match = re.match(r'([A-G][#b]?)', pitch)
        if match:
            pitch_classes.add(match.group(1))
    
    return pitch_classes


def get_lowest_pitch_in_staff(root: ET.Element, staff_n: str,
                              include_grace: bool = True) -> Optional[str]:
    """
    Find the lowest pitch in a staff.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number
        include_grace: Whether to include grace notes
        
    Returns:
        The lowest pitch in scientific notation
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


def _collect_notes_with_timing(root: ET.Element, staff_n: str,
                                include_grace: bool = True,
                                return_highest_in_chord: bool = True) -> List[Tuple[Tuple[int, float, int], ET.Element, Optional[ET.Element]]]:
    """
    Collect all notes in a staff with their timing information for sorting.
    
    This is a shared helper for get_first_note_in_staff and get_last_note_in_staff.
    
    Timing is represented as a tuple: (measure_index, tstamp, doc_order)
    - measure_index: 0-based index of the measure in the passage
    - tstamp: beat position within measure (from @tstamp attribute)
    - doc_order: document order within measure (for breaking ties and grace notes)
    
    For grace notes without tstamp:
    - If they appear before any note with tstamp in the same measure, they get
      tstamp = -0.001 * (distance from first timed note), preserving their order
    - If they appear after notes with tstamp, they get the tstamp of the preceding
      timed note + 0.001 * position, so they sort just after that note
    
    Args:
        root: The MEI document root element
        staff_n: The staff number to search
        include_grace: Whether to include grace notes
        return_highest_in_chord: For chords, return only the highest note
        
    Returns:
        List of (timing_tuple, note_element, parent_chord_or_none)
    """
    # First pass: collect all notes with their raw timing info
    # Format: (measure_idx, doc_order_in_measure, tstamp_or_none, note, parent_chord)
    raw_notes: List[Tuple[int, int, Optional[float], ET.Element, Optional[ET.Element]]] = []
    rdg_ids = _get_rdg_descendant_ids(root)

    measure_idx = 0
    for measure in root.iter(f"{{{MEI_NS}}}measure"):
        doc_order = 0

        for staff in measure.iter(f"{{{MEI_NS}}}staff"):
            staff_num = staff.get("n")
            if staff_num != staff_n:
                continue

            # Also check for cross-staff notes (notes with staff="X" attribute)
            # that might belong to this staff

            for layer in staff.iter(f"{{{MEI_NS}}}layer"):
                # Track notes we've seen in chords to avoid double-counting
                notes_in_chords: Set[str] = set()

                # First, identify all notes that are inside chords
                for chord in layer.iter(f"{{{MEI_NS}}}chord"):
                    if id(chord) in rdg_ids:
                        continue
                    for note in chord.iter(f"{{{MEI_NS}}}note"):
                        note_id = get_xml_id(note)
                        if note_id:
                            notes_in_chords.add(note_id)

                # Now iterate through all elements in document order
                for elem in layer.iter():
                    if id(elem) in rdg_ids:
                        continue
                    if not is_visible(elem):
                        continue

                    if elem.tag == f"{{{MEI_NS}}}chord":
                        tstamp_str = elem.get("tstamp")
                        tstamp = float(tstamp_str) if tstamp_str else None

                        chord_notes = [n for n in elem.iter(f"{{{MEI_NS}}}note")
                                      if is_visible(n) and id(n) not in rdg_ids]
                        if not chord_notes:
                            doc_order += 1
                            continue

                        # Filter out grace notes if needed
                        if not include_grace:
                            chord_notes = [n for n in chord_notes if not is_grace_note(n)]

                        if not chord_notes:
                            doc_order += 1
                            continue

                        if return_highest_in_chord:
                            # Find highest pitched note in chord
                            highest = None
                            highest_midi = -float('inf')
                            for note in chord_notes:
                                pitch = parse_mei_pitch(note)
                                if pitch:
                                    midi = pitch_to_midi(pitch)
                                    if midi > highest_midi:
                                        highest_midi = midi
                                        highest = note
                            if highest is not None:
                                raw_notes.append((measure_idx, doc_order, tstamp, highest, elem))
                        else:
                            # Use first visible note in chord
                            raw_notes.append((measure_idx, doc_order, tstamp, chord_notes[0], elem))

                        doc_order += 1

                    elif elem.tag == f"{{{MEI_NS}}}note":
                        # Skip notes that are inside chords (handled above)
                        note_id = get_xml_id(elem)
                        if note_id and note_id in notes_in_chords:
                            continue

                        # Skip grace notes if not including them
                        if not include_grace and is_grace_note(elem):
                            doc_order += 1
                            continue

                        tstamp_str = elem.get("tstamp")
                        tstamp = float(tstamp_str) if tstamp_str else None

                        raw_notes.append((measure_idx, doc_order, tstamp, elem, None))
                        doc_order += 1

        measure_idx += 1

    # Check for cross-staff notes: notes in other staff elements with staff="N" attribute
    measure_idx = 0
    for measure in root.iter(f"{{{MEI_NS}}}measure"):
        doc_order_offset = CROSS_STAFF_DOC_ORDER_OFFSET

        for staff in measure.iter(f"{{{MEI_NS}}}staff"):
            staff_elem_n = staff.get("n")
            if staff_elem_n == staff_n:
                continue  # Skip our target staff (already processed)

            for layer in staff.iter(f"{{{MEI_NS}}}layer"):
                for elem in layer.iter():
                    if id(elem) in rdg_ids:
                        continue
                    if elem.tag == f"{{{MEI_NS}}}note":
                        # Check if this note has staff attribute pointing to our target
                        note_staff = elem.get("staff")
                        if note_staff == staff_n:
                            if not include_grace and is_grace_note(elem):
                                doc_order_offset += 1
                                continue

                            tstamp_str = elem.get("tstamp")
                            tstamp = float(tstamp_str) if tstamp_str else None
                            raw_notes.append((measure_idx, doc_order_offset, tstamp, elem, None))
                            doc_order_offset += 1

        measure_idx += 1
    
    if not raw_notes:
        return []
    
    # Second pass: compute effective tstamp for notes without tstamp
    # Group by measure and process each measure
    from collections import defaultdict
    by_measure: Dict[int, List[Tuple[int, Optional[float], ET.Element, Optional[ET.Element]]]] = defaultdict(list)
    
    for m_idx, doc_order, tstamp, note, parent in raw_notes:
        by_measure[m_idx].append((doc_order, tstamp, note, parent))
    
    result: List[Tuple[Tuple[int, float, int], ET.Element, Optional[ET.Element]]] = []
    
    for m_idx in sorted(by_measure.keys()):
        notes = by_measure[m_idx]
        # Sort by doc_order to process in document order
        notes.sort(key=lambda x: x[0])
        
        # Find all notes with tstamp to create reference points
        timed_notes = [(doc, ts) for doc, ts, _, _ in notes if ts is not None]
        
        if not timed_notes:
            # No notes with tstamp in this measure - use doc order as pseudo-tstamp
            for doc_order, _, note, parent in notes:
                result.append(((m_idx, float(doc_order), doc_order), note, parent))
        else:
            # Sort timed notes by doc order
            timed_notes.sort()
            first_timed_doc = timed_notes[0][0]
            first_timed_ts = timed_notes[0][1]
            
            # Build a map of doc_order -> tstamp for timed notes
            timed_map = {doc: ts for doc, ts in timed_notes}
            
            for doc_order, tstamp, note, parent in notes:
                if tstamp is not None:
                    # Note has explicit tstamp
                    effective_ts = tstamp
                else:
                    # Note without tstamp (usually grace note)
                    if doc_order < first_timed_doc:
                        # Before first timed note: assign negative offset from first tstamp
                        # Distance from first timed note determines position
                        offset = (first_timed_doc - doc_order) * GRACE_NOTE_TSTAMP_INCREMENT
                        effective_ts = first_timed_ts - offset
                    else:
                        # After or between timed notes: find preceding timed note
                        preceding_ts = first_timed_ts
                        for t_doc, t_ts in timed_notes:
                            if t_doc < doc_order:
                                preceding_ts = t_ts
                            else:
                                break
                        # Assign small offset after preceding note
                        offset = GRACE_NOTE_TSTAMP_INCREMENT * (doc_order - first_timed_doc + 1)
                        effective_ts = preceding_ts + offset
                
                result.append(((m_idx, effective_ts, doc_order), note, parent))
    
    return result


def get_first_note_in_staff(root: ET.Element, staff_n: str,
                            include_grace: bool = True,
                            return_highest_in_chord: bool = True) -> Optional[Tuple[ET.Element, Optional[ET.Element]]]:
    """
    Get the first note element in a staff (by temporal position), along with its parent chord if any.
    
    Uses a combination of measure order, tstamp attribute, and document order to determine
    the correct temporal ordering. Handles grace notes (with or without tstamp),
    multi-layer passages, and cross-staff notation.
    
    For multiple notes at the same time position (same measure and tstamp), returns
    the highest pitched note if return_highest_in_chord is True.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number
        include_grace: Whether to include grace notes
        return_highest_in_chord: If first note is in chord, return highest pitch
        
    Returns:
        Tuple of (note_element, parent_chord_or_None), or None if no notes
    """
    candidates = _collect_notes_with_timing(root, staff_n, include_grace, return_highest_in_chord)
    
    if not candidates:
        return None
    
    # Find the minimum time position (measure_idx, tstamp) ignoring doc_order
    # Notes at the same (measure, tstamp) are considered simultaneous
    min_time = min((timing[0], timing[1]) for timing, _, _ in candidates)
    
    # Get all notes at that time position
    simultaneous = [(timing, note, parent) for timing, note, parent in candidates 
                    if (timing[0], timing[1]) == min_time]
    
    # Among simultaneous notes, pick highest pitch
    best = None
    best_midi = -float('inf')
    for timing, note, parent in simultaneous:
        pitch = parse_mei_pitch(note)
        midi = pitch_to_midi(pitch) if pitch else 0
        if midi > best_midi:
            best_midi = midi
            best = (note, parent)
    
    return best


def get_last_note_in_staff(root: ET.Element, staff_n: str,
                           include_grace: bool = True,
                           return_highest_in_chord: bool = True) -> Optional[Tuple[ET.Element, Optional[ET.Element]]]:
    """
    Get the last note element in a staff (by temporal position), along with its parent chord if any.
    
    Uses a combination of measure order, tstamp attribute, and document order to determine
    the correct temporal ordering. Handles grace notes (with or without tstamp),
    multi-layer passages, and cross-staff notation.
    
    For multiple notes at the same time position (same measure and tstamp), returns
    the highest pitched note if return_highest_in_chord is True.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number
        include_grace: Whether to include grace notes
        return_highest_in_chord: If last note is in chord, return highest pitch
        
    Returns:
        Tuple of (note_element, parent_chord_or_None), or None if no notes
    """
    candidates = _collect_notes_with_timing(root, staff_n, include_grace, return_highest_in_chord)
    
    if not candidates:
        return None
    
    # Find the maximum time position (measure_idx, tstamp) ignoring doc_order
    # Notes at the same (measure, tstamp) are considered simultaneous
    max_time = max((timing[0], timing[1]) for timing, _, _ in candidates)
    
    # Get all notes at that time position
    simultaneous = [(timing, note, parent) for timing, note, parent in candidates 
                    if (timing[0], timing[1]) == max_time]
    
    # Among simultaneous notes, pick highest pitch
    best = None
    best_midi = -float('inf')
    for timing, note, parent in simultaneous:
        pitch = parse_mei_pitch(note)
        midi = pitch_to_midi(pitch) if pitch else 0
        if midi > best_midi:
            best_midi = midi
            best = (note, parent)
    
    return best


def get_first_note_pitch(root: ET.Element, staff_n: str,
                         include_grace: bool = True) -> Optional[str]:
    """
    Get the pitch of the first note in a staff.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number
        include_grace: Whether to include grace notes
        
    Returns:
        Pitch in scientific notation, or None if no notes
    """
    result = get_first_note_in_staff(root, staff_n, include_grace)
    if result is not None:
        note, _ = result
        return parse_mei_pitch(note)
    return None


def get_first_note_duration(root: ET.Element, staff_n: str,
                            include_grace: bool = True) -> Optional[float]:
    """
    Get the duration of the first note in a staff.
    
    Per system prompt: "Always consider grace notes and ornaments to be the 
    same as normal notes." So we return the notated duration even for grace notes.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number
        include_grace: Whether to include grace notes (their dur is returned even though timing=0)
        
    Returns:
        Duration in quarter notes, or None if no notes
    """
    result = get_first_note_in_staff(root, staff_n, include_grace)
    if result is None:
        return None
    
    note, parent_chord = result
    
    # Get tuplet ratio if inside a tuplet
    tuplet_ratio = _get_element_tuplet_ratio(note, root)
    
    # Get parent chord's duration info if applicable
    parent_dur = None
    parent_dots = 0
    if parent_chord is not None:
        parent_dur = parent_chord.get("dur")
        dots_str = parent_chord.get("dots")
        parent_dots = int(dots_str) if dots_str else 0
    
    # Parse duration - grace notes should return their notated value for Q9
    return parse_mei_duration(note, tuplet_ratio, parent_dur, parent_dots, grace_has_duration=True)


def _get_element_tuplet_ratio(element: ET.Element, root: ET.Element) -> float:
    """
    Calculate tuplet ratio for an element by checking ancestor tuplets.
    
    This is a workaround since ElementTree doesn't maintain parent references.
    We search for the element's xml:id in tuplet descendants.
    
    Args:
        element: The target element
        root: The document root
        
    Returns:
        Tuplet ratio (e.g., 2/3 for triplets), or 1.0 if not in tuplet
    """
    element_id = get_xml_id(element)
    if not element_id:
        return 1.0
    
    # Check all tuplets to see if this element is inside one
    for tuplet in root.iter(f"{{{MEI_NS}}}tuplet"):
        # Check if our element is a descendant of this tuplet
        for desc in tuplet.iter():
            if get_xml_id(desc) == element_id:
                # Found it - calculate ratio
                num = int(tuplet.get("num", 3))
                numbase = int(tuplet.get("numbase", 2))
                return numbase / num
    
    return 1.0


def get_all_note_durations_in_staff(root: ET.Element, staff_n: str,
                                    include_grace: bool = False,
                                    sum_ties: bool = True) -> List[float]:
    """
    Get all note durations from a staff.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number
        include_grace: Whether to include grace notes (default False - they're durationless)
        sum_ties: Whether to sum tied note durations together
        
    Returns:
        List of durations in quarter notes
    """
    durations = []
    tied_ends = _get_tied_end_note_ids(root) if sum_ties else set()
    tie_pairs = _get_tied_note_pairs(root) if sum_ties else []
    rdg_ids = _get_rdg_descendant_ids(root)
    tie_start_set = {s for s, _ in tie_pairs}
    # Map end_id -> start_id for O(1) lookup (tie_pairs is small, but this is cleaner)
    end_to_start = {e: s for s, e in tie_pairs}

    # tie_accumulator is keyed by the *current running start* of the chain — i.e.
    # whichever note currently carries the accumulated duration. When a middle
    # note (both tie end AND tie start) is encountered, we transfer the key so
    # the next tie in the chain finds it.
    tie_accumulator: Dict[str, float] = {}

    # Track notes we've already processed (as part of chords)
    processed_note_ids: Set[str] = set()

    # Process all staves with the target number
    for staff in root.iter(f"{{{MEI_NS}}}staff"):
        if staff.get("n") != staff_n:
            continue

        # Process notes and chords in document order
        for elem in staff.iter():
            if id(elem) in rdg_ids:
                continue
            if not is_visible(elem):
                continue

            notes_to_process = []
            chord_dur = None
            chord_dots = 0

            if elem.tag == f"{{{MEI_NS}}}chord":
                # Get chord's duration and dots to pass to child notes
                chord_dur = elem.get("dur")
                chord_dots_str = elem.get("dots")
                chord_dots = int(chord_dots_str) if chord_dots_str else 0
                for n in elem.iter(f"{{{MEI_NS}}}note"):
                    if id(n) in rdg_ids:
                        continue
                    if is_visible(n):
                        notes_to_process.append((n, chord_dur, chord_dots))
                        # Mark these notes as processed
                        n_id = get_xml_id(n)
                        if n_id:
                            processed_note_ids.add(n_id)
            elif elem.tag == f"{{{MEI_NS}}}note":
                # Skip notes we've already processed as part of a chord
                note_id = get_xml_id(elem)
                if note_id and note_id in processed_note_ids:
                    continue
                notes_to_process = [(elem, None, 0)]
            else:
                continue

            for note, parent_dur, parent_dots in notes_to_process:
                # Skip grace notes if not including them
                if not include_grace and is_grace_note(note):
                    continue

                note_id = get_xml_id(note)
                tuplet_ratio = _get_element_tuplet_ratio(note, root)
                dur = parse_mei_duration(note, tuplet_ratio, parent_dur, parent_dots)

                if sum_ties and note_id:
                    if note_id in tied_ends:
                        start_id = end_to_start.get(note_id)
                        if start_id is not None and start_id in tie_accumulator:
                            running_key = start_id
                            tie_accumulator[running_key] += dur
                        else:
                            # Tie started before our passage — seed a new chain.
                            running_key = note_id
                            tie_accumulator[running_key] = dur

                        if note_id in tie_start_set:
                            # Middle of a chain: transfer the accumulator to
                            # this note's id so the next tie-end finds it.
                            if running_key != note_id:
                                tie_accumulator[note_id] = tie_accumulator.pop(running_key)
                        else:
                            # End of chain: emit total and clear.
                            durations.append(tie_accumulator.pop(running_key))
                    elif note_id in tie_start_set:
                        # Start of a fresh chain.
                        tie_accumulator[note_id] = dur
                    else:
                        # Regular note.
                        durations.append(dur)
                else:
                    # Not summing ties
                    durations.append(dur)

    # Handle any remaining ties (ties that extend beyond the passage)
    for start_id, dur in tie_accumulator.items():
        durations.append(dur)

    return durations


def get_longest_duration_in_staff(root: ET.Element, staff_n: str,
                                  sum_ties: bool = True) -> Optional[float]:
    """
    Find the longest note duration in a staff.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number
        sum_ties: Whether to sum tied note durations
        
    Returns:
        Longest duration in quarter notes
    """
    durations = get_all_note_durations_in_staff(root, staff_n, 
                                                 include_grace=False, 
                                                 sum_ties=sum_ties)
    return max(durations) if durations else None


def get_interval_first_last(root: ET.Element, staff_n: str,
                            include_grace: bool = True) -> Optional[int]:
    """
    Calculate the interval between first and last notes in a staff.
    
    For chords, uses the highest pitched note.
    Returns absolute value of semitones.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number
        include_grace: Whether to include grace notes
        
    Returns:
        Interval in semitones (absolute value), or None if not enough notes
    """
    first_result = get_first_note_in_staff(root, staff_n, include_grace, 
                                            return_highest_in_chord=True)
    last_result = get_last_note_in_staff(root, staff_n, include_grace,
                                          return_highest_in_chord=True)
    
    if first_result is None or last_result is None:
        return None
    
    first_note, _ = first_result
    last_note, _ = last_result
    
    first_pitch = parse_mei_pitch(first_note)
    last_pitch = parse_mei_pitch(last_note)
    
    if not first_pitch or not last_pitch:
        return None
    
    # If first and last are the same note, interval is 0
    if get_xml_id(first_note) == get_xml_id(last_note):
        return 0
    
    return calculate_interval_semitones(first_pitch, last_pitch)


def parse_mei_file(file_path: str) -> ET.Element:
    """
    Parse an MEI file and return the root element.
    
    Args:
        file_path: Path to the MEI file
        
    Returns:
        The root Element
    """
    tree = ET.parse(file_path)
    return tree.getroot()


# Convenience functions that take file paths instead of root elements
# These are used by Q1 and Q2 for simpler extraction patterns

def count_lower_staff_notes(file_path: str, **kwargs) -> int:
    """Count notes in the lower staff (staff 2)."""
    root = parse_mei_file(file_path)
    return count_notes_in_staff(root, LOWER_STAFF, **kwargs)


def count_upper_staff_notes(file_path: str, **kwargs) -> int:
    """Count notes in the upper staff (staff 1)."""
    root = parse_mei_file(file_path)
    return count_notes_in_staff(root, UPPER_STAFF, **kwargs)

# MusicXML Extractor Implementation Plan

## Overview
Building native MusicXML answer extractors for the 9 question types. This is our proof-of-concept format before extending to ABC, MEI, and Humdrum.

---

## MusicXML Structure Primer

### Key Elements We'll Parse:

```xml
<score-partwise>
  <part id="P1">  <!-- Each part = one instrument/staff system -->
    <measure number="1">
      <attributes>
        <divisions>4</divisions>  <!-- Quarter note = 4 divisions -->
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      
      <note>
        <pitch>
          <step>C</step>
          <octave>5</octave>
        </pitch>
        <duration>4</duration>  <!-- 4 divisions = quarter note -->
        <type>quarter</type>
        <staff>1</staff>  <!-- 1=upper staff, 2=lower staff -->
        <notations>
          <tied type="start"/>
          <ornaments><trill/></ornaments>
        </notations>
      </note>
      
      <note>
        <rest/>
        <duration>4</duration>
        <type>quarter</type>
        <staff>2</staff>
      </note>
    </measure>
  </part>
</score-partwise>
```

### Critical Parsing Details:

1. **Staff Numbers**: `<staff>1</staff>` = upper staff, `<staff>2</staff>` = lower staff
2. **Duration**: `<duration>` in divisions (need `<divisions>` to convert to beats)
3. **Pitch**: `<step>` + `<alter>` + `<octave>` → e.g., "C#5"
4. **Ties**: `<tied type="start"/>` or `<tied type="stop"/>`
5. **Grace Notes**: `<grace/>` element
6. **Rests**: `<rest/>` instead of `<pitch>`

---

## The 9 Question Types

From our database analysis, here are the 9 question types we need to implement:

### 1. **Count Notes in Staff**
**Question**: "How many notes are in the [upper/lower] staff in this passage?"
**Answer Type**: Integer (e.g., "8")
**Logic**:
- Count `<note>` elements where `<staff>` matches target
- Exclude if `<rest/>` present
- Include grace notes (`<grace/>`)
- Skip tied continuation notes (`<tied type="stop"/>`)

### 2. **Count Specific Note Types** 
**Question**: "How many [sixteenth/half/quarter] notes appear in the [upper/lower] staff?"
**Answer Type**: Integer
**Logic**:
- Filter `<note>` by `<type>` element (e.g., `<type>16th</type>`)
- Apply same tie/grace rules

### 3. **Count Rests**
**Question**: "How many rests are in this passage?"
**Answer Type**: Integer
**Logic**:
- Count `<note>` elements with `<rest/>`

### 4. **First Note Pitch**
**Question**: "What is the pitch of the first note in the [upper/lower] staff? If there are multiple simultaneous occurrences, choose the highest note."
**Answer Type**: Pitch notation (e.g., "C#5")
**Logic**:
- Find first `<note>` in staff (chronological order by measure/position)
- **If multiple notes occur simultaneously (same measure, same time position), choose the HIGHEST pitch**
- Extract `<step>`, `<alter>`, `<octave>`
- Format as "C#5" or "Bb3"

### 5. **Extreme Pitches**
**Question**: "What is the pitch of the [highest/lowest] note in the [upper/lower] staff?"
**Answer Type**: Pitch notation
**Logic**:
- Collect all pitches in staff
- Convert to MIDI numbers for comparison
- Return highest/lowest

### 6. **Intervals**
**Question**: "What is the interval in semitones between the first and last notes of the [upper/lower] staff?"
**Answer Type**: Integer (semitones)
**Logic**:
- Get first and last note pitches
- Calculate semitone distance

### 7. **Longest Note Duration**
**Question**: "What is the duration of the longest note in this passage? Respond in the number of beats. Use decimals only when necessary (e.g., 4, 2.25)."
**Answer Type**: Beats as string - integers without decimals (e.g., "2", "4"), decimals only when needed (e.g., "1.5", "2.25")
**Logic**:
- Convert all `<duration>` to beats using `<divisions>`
- Find maximum
- Format as integer string if whole number ("2" not "2.0"), otherwise use decimal ("1.5")

### 8. **First Note Duration**
**Question**: "What is the duration of the first note in the [upper/lower] staff? If there are multiple simultaneous occurrences, choose the highest note. Respond with a note value (e.g., Dotted eighth note)."
**Answer Type**: Named duration (e.g., "Quarter note", "Dotted eighth note", "Double dotted half note")
**Logic**:
- Get first note's `<duration>` (if simultaneous, choose highest pitch)
- Convert to beats
- Map to note name with proper dot notation

### 9. **Pitch Class Count**
**Question**: "How many different pitch classes are used in the [upper/lower] staff?"
**Answer Type**: Integer
**Logic**:
- Collect all note names (C, C#, D, etc.) ignoring octave
- Count unique pitch classes

---

## Implementation Structure

### Directory Setup
```
src/answer_extraction/
├── __init__.py
└── musicxml/
    ├── __init__.py
    ├── count_notes_in_staff.py          # Type 1
    ├── count_specific_note_types.py     # Type 2
    ├── count_rests.py                   # Type 3
    ├── first_note_pitch.py              # Type 4
    ├── extreme_pitches.py               # Type 5
    ├── intervals.py                     # Type 6
    ├── longest_note_duration.py         # Type 7
    ├── first_note_duration.py           # Type 8
    ├── pitch_class_count.py             # Type 9
    └── _helpers.py                      # Shared utilities
```

### Helper Functions (`_helpers.py`)

```python
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional

def parse_musicxml(file_path: str) -> ET.Element:
    """Parse MusicXML file and return root element."""
    tree = ET.parse(file_path)
    return tree.getroot()

def get_divisions(measure: ET.Element) -> int:
    """Get divisions value for duration calculation."""
    divisions = measure.find('.//divisions')
    return int(divisions.text) if divisions is not None else 1

def get_notes_in_range(root: ET.Element, start_measure: int, end_measure: int, 
                       staff: Optional[int] = None) -> List[ET.Element]:
    """Get all notes within measure range, optionally filtered by staff."""
    notes = []
    for part in root.findall('.//part'):
        for measure in part.findall('.//measure'):
            measure_num = int(measure.get('number', 0))
            if start_measure <= measure_num <= end_measure:
                for note in measure.findall('.//note'):
                    # Filter by staff if specified
                    if staff is not None:
                        note_staff = note.find('staff')
                        if note_staff is None or int(note_staff.text) != staff:
                            continue
                    notes.append(note)
    return notes

def is_rest(note: ET.Element) -> bool:
    """Check if note is a rest."""
    return note.find('rest') is not None

def is_grace_note(note: ET.Element) -> bool:
    """Check if note is a grace note."""
    return note.find('grace') is not None

def is_invisible_note(note: ET.Element) -> bool:
    """Check if note is invisible (formatting/spacing note)."""
    return note.get('print-object') == 'no'

def is_tied_continuation(note: ET.Element) -> bool:
    """Check if note is continuation of a tie (shouldn't be counted)."""
    tied = note.find('.//tied[@type="stop"]')
    # Only return True if this is ONLY a stop (not also a start)
    if tied is not None:
        tied_start = note.find('.//tied[@type="start"]')
        return tied_start is None
    return False

def get_pitch(note: ET.Element) -> str:
    """Extract pitch as 'C#5' or 'Bb3' format."""
    pitch_elem = note.find('pitch')
    if pitch_elem is None:
        return None
    
    step = pitch_elem.find('step').text
    octave = pitch_elem.find('octave').text
    alter = pitch_elem.find('alter')
    
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
    """Convert pitch string to MIDI number for comparison."""
    # C4 = MIDI 60 (middle C)
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

def get_duration_in_beats(note: ET.Element, divisions: int) -> float:
    """Convert duration to beats."""
    duration = note.find('duration')
    if duration is None:
        return 0.0
    return float(duration.text) / divisions

def duration_to_note_name(beats: float) -> str:
    """
    Convert beats to note name (e.g., 2.0 -> 'Half note').
    Supports single and double dots, up to 32nd notes.
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
    rounded = round(beats, 5)
    return duration_map.get(rounded, f"{beats} beats")

def get_pitch_class(pitch: str) -> str:
    """Extract pitch class (note name without octave)."""
    # Remove octave digit(s) from end
    import re
    return re.sub(r'\d+$', '', pitch)
```

---

## Example Implementation: Count Notes in Staff

**File**: `musicxml/count_notes_in_staff.py`

```python
"""Count notes in specified staff from MusicXML."""

import xml.etree.ElementTree as ET
from typing import Optional
from . import _helpers

def extract_answer(file_path: str, passage_id: str, staff: str = "upper") -> str:
    """
    Count notes in the specified staff.
    
    Args:
        file_path: Path to MusicXML file
        passage_id: Passage ID to look up measure range
        staff: "upper" or "lower"
    
    Returns:
        String representation of count (e.g., "8")
    """
    # Get format-specific measure range from database
    from core.db_utils import get_connection
    conn = get_connection()
    result = conn.execute("""
        SELECT start_measure, end_measure 
        FROM passage_measures 
        WHERE passage_id = ? AND format = 'musicxml'
    """, (passage_id,)).fetchone()
    
    if not result:
        raise ValueError(f"No measure range found for {passage_id} in MusicXML")
    
    start_measure, end_measure = result
    
    # Parse MusicXML
    root = _helpers.parse_musicxml(file_path)
    
    # Determine staff number (1 = upper, 2 = lower)
    staff_num = 1 if staff == "upper" else 2
    
    # Get all notes in range for this staff
    notes = _helpers.get_notes_in_range(root, start_measure, end_measure, staff_num)
    
    # Count notes (exclude rests, include grace notes, exclude tied continuations, exclude invisible notes)
    count = 0
    for note in notes:
        if _helpers.is_rest(note):
            continue
        if _helpers.is_tied_continuation(note):
            continue
        if _helpers.is_invisible_note(note):
            continue
        count += 1
    
    return str(count)
```

---

## Testing Strategy

### 1. Unit Tests
Create test fixtures from known passages:

```python
# tests/answer_extraction/test_musicxml/test_count_notes_in_staff.py

def test_count_notes_upper_staff_single_measure():
    # Use P-001 (known passage)
    answer = extract_answer(
        'data/musicxml/16-1.musicxml',
        passage_id='P-001',
        staff='upper'
    )
    # Compare against manual answer from database
    assert answer == "3"  # or whatever the manual answer is

def test_count_notes_lower_staff():
    answer = extract_answer(
        'data/musicxml/16-1.musicxml',
        passage_id='P-001',
        staff='lower'
    )
    assert answer == "8"
```

### 2. Validation Script
Compare all programmatic answers against manual answers:

```python
# scripts/validate_musicxml_answers.py

from answer_extraction.musicxml import count_notes_in_staff
from core.db_utils import get_connection

conn = get_connection()

# Get all questions with manual MusicXML answers
questions = conn.execute("""
    SELECT q.question_id, q.passage_id, q.question_text, q.answer_musicxml
    FROM questions q
    WHERE q.answer_musicxml IS NOT NULL
""").fetchall()

mismatches = []

for qid, pid, question, manual_answer in questions:
    # Determine which extractor to use based on question text
    # (We'll build a dispatcher for this)
    
    try:
        programmatic_answer = generate_answer(qid, pid, 'musicxml')
        
        if programmatic_answer != manual_answer:
            mismatches.append({
                'question_id': qid,
                'passage_id': pid,
                'question': question,
                'manual': manual_answer,
                'programmatic': programmatic_answer
            })
    except Exception as e:
        print(f"ERROR on {qid}: {e}")

# Generate report
print(f"\n{'='*80}")
print(f"VALIDATION REPORT: MusicXML")
print(f"{'='*80}")
print(f"Total questions: {len(questions)}")
print(f"Mismatches: {len(mismatches)}")
print(f"Match rate: {(1 - len(mismatches)/len(questions))*100:.1f}%")
```

---

## Implementation Order

### Phase 1: Foundation (Day 1)
1. ✅ Create directory structure
2. ✅ Implement `_helpers.py` with all utility functions
3. ✅ Write unit tests for helpers
4. ✅ Set up database connection utilities

### Phase 2: Simple Extractors (Day 2)
5. ✅ Implement `count_notes_in_staff.py`
6. ✅ Implement `count_rests.py`
7. ✅ Implement `first_note_pitch.py`
8. ✅ Test against known passages

### Phase 3: Complex Extractors (Day 3)
9. ✅ Implement `extreme_pitches.py`
10. ✅ Implement `intervals.py`
11. ✅ Implement `longest_note_duration.py`
12. ✅ Implement `first_note_duration.py`
13. ✅ Implement `pitch_class_count.py`
14. ✅ Implement `count_specific_note_types.py`

### Phase 4: Integration & Validation (Day 4)
15. ✅ Create question dispatcher (maps question text → extractor)
16. ✅ Run validation against all manual answers
17. ✅ Document discrepancies
18. ✅ Fix bugs and edge cases

---

## Next Steps

1. **Confirm approach**: Does this implementation plan look good?
2. **Start coding**: Begin with `_helpers.py` and `count_notes_in_staff.py`
3. **Test early**: Use one known passage to validate approach
4. **Iterate**: Build remaining extractors following same pattern

Ready to start implementing?

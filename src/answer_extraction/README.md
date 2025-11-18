# Answer Extraction Module

Programmatic answer extraction from music encoding formats.

## Overview

This module provides automated answer extraction for benchmark questions across multiple music encoding formats. Each format has its own set of extractors that parse the native format directly (no format conversion).

## Architecture

```
src/answer_extraction/
├── __init__.py                 # Module documentation
├── musicxml/                   # MusicXML extractors (implemented)
│   ├── __init__.py
│   ├── _helpers.py            # MusicXML parsing utilities
│   ├── count_notes_in_staff.py
│   ├── count_rests.py
│   ├── count_specific_note_types.py
│   ├── first_note_pitch.py
│   ├── first_note_duration.py
│   ├── extreme_pitches.py
│   ├── intervals.py
│   ├── longest_note_duration.py
│   └── pitch_class_count.py
├── abc/                        # ABC notation extractors (pending)
├── mei/                        # MEI extractors (pending)
└── humdrum/                    # Humdrum extractors (pending)
```

## Design Principles

### 1. Native Format Parsing
- **NO format conversion** - each extractor works directly with the native format
- Prevents conversion errors and lossy transformations
- Format-specific measure ranges stored in `passage_measures` table

### 2. Consistent Interface
All extractors follow the same signature:
```python
def extract_answer(file_path: str, passage_id: str, **kwargs) -> str
```

- `file_path`: Path to the music encoding file
- `passage_id`: Passage ID (e.g., 'P-001') to look up measure range
- `**kwargs`: Format/question-specific parameters (e.g., `staff='upper'`, `extremum='highest'`)
- Returns: String answer matching database format

### 3. Database Integration
Extractors query the `passage_measures` table to get format-specific measure ranges:
```python
SELECT start_measure, end_measure 
FROM passage_measures 
WHERE passage_id = ? AND format = 'musicxml'
```

This handles cases where measure numbers differ between formats for the same passage.

### 4. Extensibility
Adding new question types:
1. Implement extractor in each format subdirectory
2. Add to format's `__init__.py` exports
3. Update question dispatcher (future)
4. Add tests

Adding new formats:
1. Create format subdirectory
2. Implement `_helpers.py` with format-specific parsing
3. Implement all 9 question type extractors
4. Add to module exports

## MusicXML Extractors (Implemented)

### Question Type Coverage

| Question Type | Module | Description |
|--------------|--------|-------------|
| Note counting | `count_notes_in_staff.py` | Count notes in upper/lower staff |
| Rest counting | `count_rests.py` | Count rests in passage |
| Specific durations | `count_specific_note_types.py` | Count sixteenth/half/quarter notes |
| First pitch | `first_note_pitch.py` | Get first note pitch (highest if simultaneous) |
| First duration | `first_note_duration.py` | Get first note duration as named value |
| Extreme pitches | `extreme_pitches.py` | Get highest or lowest note |
| Intervals | `intervals.py` | Calculate interval between first and last notes |
| Longest duration | `longest_note_duration.py` | Get longest note duration in beats |
| Pitch classes | `pitch_class_count.py` | Count unique pitch classes |

### MusicXML-Specific Rules

All MusicXML extractors follow these filtering rules:

**Exclude from counts:**
- Rests (`<rest/>` element)
- Tied continuations (`<tied type="stop"/>` without `<tied type="start"/>`)
- Invisible notes (`print-object="no"` - used for formatting)

**Include in counts:**
- Grace notes (`<grace/>` element)
- Regular notes

### Helper Functions

`_helpers.py` provides comprehensive utilities:

**Parsing:**
- `parse_musicxml()` - Parse file and return root element
- `get_divisions()` - Extract divisions for duration calculation

**Filtering:**
- `get_notes_in_range()` - Get notes in measure range, optionally by staff
- `is_rest()`, `is_grace_note()`, `is_invisible_note()`, `is_tied_continuation()`

**Pitch:**
- `get_pitch()` - Extract pitch as 'C#5' or 'Bb3'
- `pitch_to_midi()` - Convert to MIDI number for comparison
- `get_pitch_class()` - Extract pitch class (note without octave)

**Duration:**
- `get_duration_in_beats()` - Convert duration to beats
- `duration_to_note_name()` - Convert beats to note name
- `format_beats()` - Format as integer if whole, decimal otherwise

## Usage Examples

### Example 1: Count Notes
```python
from src.answer_extraction.musicxml import count_notes_in_staff

answer = count_notes_in_staff.extract_answer(
    file_path='data/musicxml/16-1.xml',
    passage_id='P-001',
    staff='upper'
)
print(answer)  # "8"
```

### Example 2: Get First Note Pitch
```python
from src.answer_extraction.musicxml import first_note_pitch

answer = first_note_pitch.extract_answer(
    file_path='data/musicxml/16-1.xml',
    passage_id='P-001',
    staff='lower'
)
print(answer)  # "C#5"
```

### Example 3: Find Highest Note
```python
from src.answer_extraction.musicxml import extreme_pitches

answer = extreme_pitches.extract_answer(
    file_path='data/musicxml/16-1.xml',
    passage_id='P-001',
    extremum='highest',
    staff='upper'
)
print(answer)  # "G6"
```

### Example 4: Calculate Interval
```python
from src.answer_extraction.musicxml import intervals

answer = intervals.extract_answer(
    file_path='data/musicxml/16-1.xml',
    passage_id='P-001',
    staff='upper'
)
print(answer)  # "7" (perfect fifth up)
```

## Command-Line Usage

Each extractor can be run standalone:

```bash
# Count notes
python src/answer_extraction/musicxml/count_notes_in_staff.py \
    data/musicxml/16-1.xml P-001 upper

# Get first note pitch
python src/answer_extraction/musicxml/first_note_pitch.py \
    data/musicxml/16-1.xml P-001 lower

# Find highest note
python src/answer_extraction/musicxml/extreme_pitches.py \
    data/musicxml/16-1.xml P-001 highest upper
```

## Testing Strategy

### Unit Tests (Future)
```python
# tests/answer_extraction/musicxml/test_count_notes_in_staff.py
def test_count_notes_upper_staff():
    answer = count_notes_in_staff.extract_answer(
        'data/musicxml/16-1.xml',
        'P-001',
        'upper'
    )
    assert answer == "3"  # Compare against manual answer
```

### Validation (Future)
Compare programmatic answers against manual answers from database:
```python
# scripts/validate_musicxml_answers.py
# - Query all questions with manual MusicXML answers
# - Run appropriate extractor for each question
# - Compare programmatic vs manual answers
# - Generate match rate report
```

## Future Work

### ABC Notation
- Implement custom ABC parser
- Handle ABC-specific syntax (meter, key signatures in header)
- Map ABC note durations to standard values

### MEI (Music Encoding Initiative)
- Use XML parsing similar to MusicXML
- Handle MEI-specific elements (<note>, <rest>, <chord>)
- Support MEI's staff/layer structure

### Humdrum **kern
- Implement line-based parser for **kern format
- Parse spine structure (multiple voices/staves)
- Handle kern-specific pitch/duration encoding

### Question Dispatcher
Create intelligent dispatcher that maps question text to appropriate extractor:
```python
def dispatch_question(question_text: str, file_path: str, passage_id: str, format: str):
    """Route question to appropriate extractor based on question text."""
    if "how many notes" in question_text.lower():
        if "upper staff" in question_text.lower():
            return extractors[format].count_notes_in_staff(file_path, passage_id, 'upper')
    # ... etc
```

## Notes

- **Database dependency**: All extractors require access to `benchmark.db` via `src/db_utils.py`
- **Measure ranges**: Uses `passage_measures` table for format-specific ranges
- **Error handling**: Raises `ValueError` with descriptive messages for missing data
- **Format validation**: Each extractor validates input parameters
- **Documentation**: Every function has comprehensive docstrings

## Maintenance

When adding new question types:
1. Add to all 4 formats (maintain parity)
2. Update this README with new question type
3. Add to format `__init__.py` exports
4. Create tests
5. Update validation scripts

When adding new formats:
1. Study format specification
2. Create `_helpers.py` with parsing utilities
3. Implement all 9 extractors
4. Test against existing passages
5. Document format-specific gotchas

# Answer Extraction Module

This module provides programmatic ground truth extraction for the Music Encoding Benchmark. It parses music notation files in multiple formats and extracts answers to standardized questions about the musical content.

## Overview

The module extracts answers from four music encoding formats:
- **ABC** (`abc/`) - ABC notation files (.abc)
- **Humdrum** (`humdrum/`) - Humdrum/kern files (.krn)
- **MEI** (`mei/`) - Music Encoding Initiative files (.mei)
- **MusicXML** (`musicxml/`) - MusicXML files (.xml)

All formats implement the same 9 questions, allowing cross-format validation of extraction accuracy.

## Implemented Questions

| ID | Question | Description |
|----|----------|-------------|
| Q1 | Note count (lower staff) | Count notes in bass/left-hand staff, including grace notes, ties counted once |
| Q2 | Note count (upper staff) | Count notes in treble/right-hand staff, including grace notes, ties counted once |
| Q3 | First pitch (upper staff) | Scientific pitch notation (e.g., "C5", "F#4") of the first note |
| Q4 | Lowest pitch (lower staff) | Scientific pitch notation of the lowest sounding pitch |
| Q5 | Longest duration | Duration in quarter notes of the longest note (ties summed) |
| Q6 | Pitch class count | Number of unique pitch classes (C, C#, D, etc.) across both staves |
| Q7 | Interval (first to last) | Semitones between first and last notes in upper staff |
| Q8 | Rest count | Number of visible rests (excluding invisible/spacing rests) |
| Q9 | First note duration | Duration in quarter notes of the first note in lower staff |

## Architecture

```
answer_extraction/
├── __init__.py
├── registry.py          # Extractor registration system
├── core/                 # Format-agnostic utilities
│   ├── duration.py       # Duration formatting
│   └── pitch.py          # Pitch/interval calculation
├── abc/                  # ABC notation extractors
│   ├── __init__.py
│   ├── utils.py          # ABC parsing utilities
│   └── q1_*.py ... q9_*.py
├── humdrum/              # Humdrum/kern extractors
│   ├── __init__.py
│   ├── utils.py          # Humdrum parsing utilities
│   └── q1_*.py ... q9_*.py
├── mei/                  # MEI extractors
│   ├── __init__.py
│   ├── utils.py          # MEI parsing utilities (~1100 lines)
│   └── q1_*.py ... q9_*.py
└── musicxml/             # MusicXML extractors
    ├── __init__.py
    ├── utils.py          # MusicXML parsing utilities (~1500 lines)
    └── q1_*.py ... q9_*.py
```

### Registry Pattern

All extractors use the `@register_extractor` decorator for automatic discovery:

```python
from ..registry import register_extractor

@register_extractor(1, "mei")  # question_id, format_name
def extract(file_path: str) -> str:
    """Extract answer and return as string."""
    return answer
```

### Core Utilities

**`core/pitch.py`**
- `pitch_to_midi(scientific_pitch)` - Convert "C4" → 60
- `calculate_interval_semitones(pitch1, pitch2)` - Calculate interval

**`core/duration.py`**
- `format_duration(quarter_notes)` - Format with proper rounding (0.25, 0.5, 1, etc.)

## Edge Cases Handled

All formats correctly handle these edge cases:

| Edge Case | ABC | Humdrum | MEI | MusicXML |
|-----------|-----|---------|-----|----------|
| Grace notes | ✅ | ✅ | ✅ | ✅ |
| Tied notes (count once) | ✅ | ✅ | ✅ | ✅ |
| Tied notes (sum durations) | ✅ | ✅ | ✅ | ✅ |
| Chords | ✅ | ✅ | ✅ | ✅ |
| Tuplets | ✅ | ✅ | ✅ | ✅ |
| Invisible rests | ✅ | ✅ | ✅ | ✅ |
| Multiple voices per staff | ✅ | ✅ | ✅ | ✅ |
| Cross-staff notes | N/A* | N/A* | ✅ | ✅ |
| Accidentals | ✅ | ✅ | ✅ | ✅ |

*ABC and Humdrum use voice-based encoding where cross-staff is implicit.

## Format-Specific Details

### ABC Notation

**Staff Detection:**
- Uses `%%staves` directive to map voices to staves
- Example: `%%staves {V1 V2} {V3 V4}` → V1,V2 = upper; V3,V4 = lower
- Falls back to voice numbering if no staves directive

**Grace Notes:**
- Single grace: 1 beam (0.5 quarter notes)
- Multiple grace: 2 beams (0.25 quarter notes)
- `/` modifier adds beams: `{C/}` = 3 beams (0.125 qtr)

**Ties:**
- Indicated by `-` after note: `C-C` = tied C
- Tracked by pitch for correct counting

### Humdrum (**kern)

**Staff Detection:**
- Leftmost `**kern` spine = lower staff (bass)
- Rightmost `**kern` spine = upper staff (treble)
- Handles spine splits (`*^`) and merges (`*v`)

**Grace Notes:**
- Indicated by `q` or `Q` in token
- Acciaccatura vs. appoggiatura distinguished

**Ties:**
- `[` starts tie, `]` ends tie, `_` continues
- Duration summed across tie chain

### MEI (Music Encoding Initiative)

**Staff Detection:**
- `<staff n="1">` = upper staff
- `<staff n="2">` = lower staff
- Cross-staff notes have `@staff` attribute pointing to display staff

**Grace Notes:**
- `<note grace="acc">` or `<note grace="unacc">`
- Excluded from duration calculations

**Ties:**
- `@tie="i"` (initial), `@tie="m"` (medial), `@tie="t"` (terminal)
- Also supports `<tie>` elements with `@xml:id` references

**Visibility:**
- `@visible="false"` excludes elements from counts

### MusicXML

**Encoding Styles:**
1. **Explicit staves:** Single `<part>` with `<staves>2</staves>`, notes have `<staff>1</staff>` or `<staff>2</staff>`
2. **Separate parts:** Two `<part>` elements (P1=upper, P2=lower), no `<staff>` elements needed

**Cross-Staff Notes:**
- Notes can have `<staff>` element pointing to different staff
- Handled with `CROSS_STAFF_POSITION_OFFSET` for proper ordering

**Duration Calculation:**
- Primary: `<duration>` / `<divisions>` = quarter notes
- Fallback: `<type>` element (quarter, eighth, etc.) when `<duration>` missing

**Ties:**
- `<tie type="start"/>` and `<tie type="stop"/>` elements
- Tracked by (measure, position, pitch) tuple

**Visibility:**
- `print-object="no"` excludes elements from counts

## Testing

Tests are in `tests/test_all_extractors.py` and use verified answers from the database.

```bash
# Run all tests
python -m pytest tests/test_all_extractors.py -v

# Run specific format
python -m pytest tests/test_all_extractors.py -k "humdrum" -v

# Run specific question
python -m pytest tests/test_all_extractors.py -k "Q5" -v

# Run with coverage
python -m pytest tests/test_all_extractors.py --cov=src/answer_extraction
```

### Test Data

- **Passages:** `passages/{format}/P-XXX.{ext}`
- **Ground Truth:** `benchmark.db` → `questions` table with verified answers
- **45 passages** verified for each format (P-001 through P-045)

## Adding New Extractors

### 1. Create the Extractor

```python
# src/answer_extraction/{format}/q{N}_{description}.py

"""
Q{N}: {Question text}

{Additional notes about what to include/exclude}
"""

from ..registry import register_extractor
from .utils import helper_function

@register_extractor({N}, "{format}")
def extract(file_path: str) -> str:
    """
    Extract answer from file.
    
    Args:
        file_path: Path to the notation file
        
    Returns:
        Answer as a string
    """
    # Implementation
    return str(answer)
```

### 2. Update `__init__.py`

```python
from . import q{N}_{description}
```

### 3. Add Database Entry

```sql
INSERT INTO question_types (id, question_text, expected_answer_format)
VALUES ({N}, 'Question text?', 'format description');
```

### 4. Verify Across Formats

Run extractors on test passages and verify cross-format consistency:

```python
from src.answer_extraction import get_extractor

for format in ['abc', 'humdrum', 'mei', 'musicxml']:
    extractor = get_extractor(N, format)
    result = extractor(f'passages/{format}/P-001.{ext}')
    print(f'{format}: {result}')
```

## Validation

The verification script checks cross-format consistency:

```bash
python scripts/utilities/verify_cross_format.py --passages P-001,P-002,P-003
```

This compares extracted answers across formats and reports discrepancies, which may indicate:
1. Bugs in extractors
2. Genuine encoding differences between formats
3. Missing or incorrect ground truth

## Performance

Typical extraction times (per passage):
- ABC: ~5ms
- Humdrum: ~10ms
- MEI: ~15ms
- MusicXML: ~20ms

All 405 passage/question combinations (45 passages × 9 questions) run in under 1 second.

## Function Naming Conventions

### Public Functions (used by extractors)

| Purpose | ABC | Humdrum | MEI | MusicXML |
|---------|-----|---------|-----|----------|
| Count notes | `count_notes_for_voices()` | `count_notes_in_spine()` | `count_notes_in_staff()` | `count_notes_in_staff()` |
| Get all pitches | `extract_all_pitches_from_content()` | `get_all_pitches_in_spine()` | `_get_all_pitches_in_staff()` | `_get_all_pitches_in_staff()` |
| Parse single pitch | `abc_pitch_to_scientific()` | `parse_kern_pitch()` | `parse_mei_pitch()` | `parse_musicxml_pitch()` |
| Parse duration | `parse_duration_suffix()` | `parse_kern_duration()` | `parse_mei_duration()` | `parse_musicxml_duration()` |
| Get first note | `get_first_pitch_for_voices()` | `get_first_note_pitch()` | `get_first_note_pitch()` | `get_first_note_pitch()` |
| Get lowest pitch | `get_lowest_pitch_for_voices()` | `get_lowest_pitch_in_spine()` | `get_lowest_pitch_in_staff()` | `get_lowest_pitch_in_staff()` |
| Check grace note | *(inline)* | `is_grace_note()` | `is_grace_note()` | `is_grace_note()` |
| Check rest | *(inline)* | `is_rest()` | *(tag check)* | `is_rest()` |

### Naming Pattern

- **ABC:** `{verb}_{noun}_for_voices()` - operates on voice content strings
- **Humdrum:** `{verb}_{noun}_in_spine()` - operates on spine token lists
- **MEI/MusicXML:** `{verb}_{noun}_in_staff()` - operates on XML elements with staff number

### Private Functions

Prefixed with `_` for internal helpers:
- `_get_tied_note_info()` - Build tie tracking structures
- `_collect_notes_with_timing()` - Gather notes with position info
- `_note_belongs_to_staff()` - Check staff membership

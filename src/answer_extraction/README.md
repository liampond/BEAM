# Answer Extraction Module

This module provides programmatic ground truth extraction for music encoding benchmark questions. It parses music notation files and extracts answers that match what a human would see in the rendered score.

## Supported Formats

- **ABC** (`abc/`) - ABC notation files (.abc)
- **Humdrum** (`humdrum/`) - Humdrum/kern files (.krn)  
- **MEI** (`mei/`) - Music Encoding Initiative files (.mei)
- **MusicXML** (`musicxml/`) - MusicXML files (.xml, .musicxml)

## Implemented Questions

| ID | Question | Status |
|----|----------|--------|
| Q1 | How many notes are in the lower staff? | ✅ ABC |
| Q2 | How many notes are in the upper staff? | ✅ ABC |
| Q3 | What is the first pitch in the upper staff? | ✅ ABC |
| Q4 | What is the lowest pitch in the lower staff? | ✅ ABC |
| Q5 | What is the longest note duration? | ✅ ABC |
| Q6 | How many unique pitch classes are there? | ✅ ABC |
| Q7 | What interval separates the first and last notes? | ✅ ABC |
| Q8 | How many rests are there? | ✅ ABC |
| Q9 | What is the duration of the first note in the lower staff? | ✅ ABC |

## Architecture

### Registry Pattern

Extractors are registered using the `@register_extractor` decorator:

```python
from ..registry import register_extractor

@register_extractor("abc", 1)  # format, question_type_id
def extract(file_path: str) -> str:
    # Extract answer from file
    return answer
```

### Core Utilities

- `core/duration.py` - Duration formatting with proper rounding
- `core/pitch.py` - Pitch parsing and interval calculation
- `utils/` - Shared utility functions

### Format-Specific Utilities

Each format has a `utils.py` with helpers for:
- Staff/voice identification
- Note/rest parsing
- Duration calculation
- Pitch extraction

## ABC Grace Note Algorithm

Grace note duration is determined by visual beam count (empirically verified with abcjs):

### Base Beams
- Single grace note: 1 beam (8th note = 0.5 quarter notes)
- Multiple grace notes: 2 beams (16th note = 0.25 quarter notes)

### Modifiers
- `/` after pitch: Adds one beam per slash
  - `{C/}` in multiple = 3 beams (32nd = 0.125 qtr)
  - `{C//}` in multiple = 4 beams (64th = 0.0625 qtr)
- Numeric (e.g., `C2`): Sets beams to 1 (8th note)
- Leading `/` (acciaccatura): Visual slash only, no duration change
- `L:` field: No effect on grace note beams

### Beam to Duration
| Beams | Note Value | Quarter Notes |
|-------|------------|---------------|
| 1 | 8th | 0.5 |
| 2 | 16th | 0.25 |
| 3 | 32nd | 0.13 |
| 4 | 64th | 0.06 |

## Testing

Tests are in `tests/abc/` with one test file per question type:

```bash
# Run all ABC tests
python -m pytest tests/abc/ -v

# Run specific question
python -m pytest tests/abc/test_q9_first_note_duration.py -v
```

Tests use verified answers from the database (`database_exports/questions.csv`).

## Adding New Extractors

1. Create `q{N}_{description}.py` in the format directory
2. Implement the `extract(file_path: str) -> str` function
3. Register with `@register_extractor("format", question_id)`
4. Create corresponding test file in `tests/{format}/`

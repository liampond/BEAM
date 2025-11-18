# Programmatic Ground Truth - Architecture & Implementation Plan v2

## Overview
Pivot from manual human-input ground truth answers to **native format-specific programmatic extraction**. This ensures:
- **Accuracy**: No conversion errors - work directly with native format
- **Scalability**: Can handle single bars to entire movements
- **Reliability**: Eliminates human error in answer verification
- **Consistency**: Same question yields same answer across all formats
- **Extensibility**: Easy to add new question types long-term

---

## Core Principle: Native Format Processing

**NO FORMAT CONVERSION** - Each format has its own dedicated answer extractors to avoid conversion errors.

### The 9 Current Question Types

From database analysis, we have these question patterns:

1. **Count notes in hand**: "How many notes are in the [left/right] hand"
2. **Count specific note types**: "How many [sixteenth/half/etc] notes appear"
3. **Count rests**: "How many rests are in this measure"
4. **First note pitch**: "What is the pitch of the first note in the [left/right] hand"
5. **Extreme pitches**: "What is the pitch of the [lowest/highest] note in the [left/right] hand"
6. **Intervals**: "What is the interval [in semitones] between the first and last notes"
7. **Longest note duration**: "What is the duration of the longest note"
8. **First note duration**: "What is the duration of the first note in the [left/right] hand"
9. **Pitch class count**: "How many different pitch classes are used in the [left/right] hand"

**Future question type example**: "How many times do the two hands play at the same time"

---

## Architecture: Format × Question Matrix

### Directory Structure

```
src/
├── answer_extraction/              # NEW: Core extraction logic
│   ├── __init__.py
│   ├── abc/                        # ABC-specific extractors
│   │   ├── __init__.py
│   │   ├── Q01_count_notes_hand.py
│   │   ├── Q02_count_note_types.py
│   │   ├── Q03_count_rests.py
│   │   ├── Q04_first_note_pitch.py
│   │   ├── Q05_extreme_pitches.py
│   │   ├── Q06_intervals.py
│   │   ├── Q07_longest_duration.py
│   │   ├── Q08_first_note_duration.py
│   │   ├── Q09_pitch_class_count.py
│   │   └── _helpers.py             # ABC-specific parsing helpers
│   │
│   ├── mei/                        # MEI-specific extractors
│   │   ├── __init__.py
│   │   ├── Q01_count_notes_hand.py
│   │   ├── Q02_count_note_types.py
│   │   ├── Q03_count_rests.py
│   │   ├── Q04_first_note_pitch.py
│   │   ├── Q05_extreme_pitches.py
│   │   ├── Q06_intervals.py
│   │   ├── Q07_longest_duration.py
│   │   ├── Q08_first_note_duration.py
│   │   ├── Q09_pitch_class_count.py
│   │   └── _helpers.py             # MEI-specific parsing helpers
│   │
│   ├── musicxml/                   # MusicXML-specific extractors
│   │   ├── __init__.py
│   │   ├── Q01_count_notes_hand.py
│   │   ├── Q02_count_note_types.py
│   │   ├── Q03_count_rests.py
│   │   ├── Q04_first_note_pitch.py
│   │   ├── Q05_extreme_pitches.py
│   │   ├── Q06_intervals.py
│   │   ├── Q07_longest_duration.py
│   │   ├── Q08_first_note_duration.py
│   │   ├── Q09_pitch_class_count.py
│   │   └── _helpers.py             # MusicXML-specific parsing helpers
│   │
│   ├── humdrum/                    # Humdrum-specific extractors
│   │   ├── __init__.py
│   │   ├── Q01_count_notes_hand.py
│   │   ├── Q02_count_note_types.py
│   │   ├── Q03_count_rests.py
│   │   ├── Q04_first_note_pitch.py
│   │   ├── Q05_extreme_pitches.py
│   │   ├── Q06_intervals.py
│   │   ├── Q07_longest_duration.py
│   │   ├── Q08_first_note_duration.py
│   │   ├── Q09_pitch_class_count.py
│   │   └── _helpers.py             # Humdrum-specific parsing helpers
│   │
│   └── common/                     # Shared utilities
│       ├── __init__.py
│       ├── pitch_utils.py          # Pitch normalization, interval calc
│       ├── duration_utils.py       # Duration naming, comparison
│       └── validation.py           # Cross-format validation
│
├── scripts/
│   ├── generate_answers.py         # NEW: Generate all answers
│   ├── validate_answers.py         # NEW: Validate against manual answers
│   └── batch_process.py            # NEW: Process entire movements
│
└── tests/
    └── answer_extraction/          # NEW: Test suite
        ├── test_abc/
        ├── test_mei/
        ├── test_musicxml/
        ├── test_humdrum/
        └── fixtures/               # Sample passages in all 4 formats
```

---

## Each Extractor Script Interface

**Every extractor follows the same interface**:

```python
def extract_answer(file_path: str, start_measure: int, end_measure: int, **params) -> str:
    """
    Extract answer for this question type from the native format file.
    
    Args:
        file_path: Path to the music file (abc, mei, musicxml, or krn)
        start_measure: Starting measure number (1-indexed)
        end_measure: Ending measure number (inclusive)
        **params: Question-specific parameters (e.g., hand="left", note_type="sixteenth")
    
    Returns:
        str: The answer in canonical format
        
    Raises:
        ExtractionError: If passage cannot be parsed
        ValidationWarning: If result needs human verification (logged, not raised)
    """
    pass
```

**Example**: `musicxml/Q01_count_notes_hand.py`
```python
import xml.etree.ElementTree as ET

def extract_answer(file_path: str, start_measure: int, end_measure: int, hand: str) -> str:
    """Count notes in specified hand from MusicXML."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    count = 0
    # Native MusicXML parsing - no conversion
    for part in root.findall('.//part'):
        for measure in part.findall('.//measure'):
            measure_num = int(measure.get('number'))
            if start_measure <= measure_num <= end_measure:
                # Determine if this part is left or right hand
                staff_num = get_staff_number(part)
                if matches_hand(staff_num, hand):
                    for note in measure.findall('.//note'):
                        if should_count_note(note):  # handles ties, grace notes
                            count += 1
    
    return str(count)
```

---

## Technology Stack - Native Format Libraries

### 1. **MusicXML** 
**Library**: `xml.etree.ElementTree` (built-in) + `music21` for complex queries
- Native XML parsing - no conversion
- Direct access to `<note>`, `<measure>`, `<part>` elements
- Staff detection via `<staff>` elements
- Duration calculation from `<duration>` and `<divisions>`

### 2. **MEI**
**Library**: `xml.etree.ElementTree` + `verovio` Python bindings (optional)
- Native XML parsing of MEI schema
- Access to `<note>`, `<measure>`, `<staff>` elements
- Duration from `@dur` attribute
- Pitch from `@pname` and `@oct` attributes

### 3. **ABC Notation**
**Library**: Custom regex-based parser + `music21.abcFormat` for validation
- Text-based format - regex patterns for notes, bars, voices
- Voice detection from `V:` headers
- Duration from note suffixes (e.g., `C/2` = half duration)
- Multi-voice handling for left/right hand

### 4. **Humdrum (Kern)**
**Library**: Custom line-by-line parser
- Spine-based processing (each column = voice/staff)
- Duration from kern note syntax (`4c` = quarter C)
- Staff detection from spine labels
- Native kern interpretation - no conversion needed

---

## Implementation Strategy

### Phase 1: Foundation & MusicXML (Week 1)
**Goal**: Prove the concept with one format, all 9 question types

1. **Set up infrastructure**
   - Create directory structure
   - Set up testing framework with fixtures
   - Create common utilities (pitch normalization, duration naming)

2. **Implement all 9 MusicXML extractors**
   - Q01-Q09 for MusicXML
   - Helper functions in `_helpers.py`
   - Unit tests for each extractor
   - Handle single bar AND entire movements from day 1

3. **Validation script**
   - Compare MusicXML answers against manual answers
   - Flag discrepancies for review
   - Generate validation report

### Phase 2: Extend to All Formats (Week 2-3)
**Goal**: Implement all 9 extractors for remaining 3 formats

4. **ABC extractors** (Q01-Q09)
   - Native ABC parsing
   - Test against manual answers
   - Cross-validate with MusicXML

5. **MEI extractors** (Q01-Q09)
   - Native MEI parsing
   - Test against manual answers
   - Cross-validate with MusicXML

6. **Humdrum extractors** (Q01-Q09)
   - Native kern parsing
   - Test against manual answers
   - Cross-validate with MusicXML

### Phase 3: Database Migration (Week 4)
**Goal**: Integrate into database and workflow

7. **Generate all answers**
   - Run extractors on all 421 questions × 4 formats
   - Populate database answer columns
   - Keep manual answers as validation dataset

8. **Build batch processing script**
   - Process entire movements (future questions)
   - Handle large score files efficiently
   - Parallel processing for speed

### Phase 4: Extensibility (Ongoing)
**Goal**: Make adding new question types trivial

9. **Add new question types**
   - Example: "How many times do hands play simultaneously"
   - Create Q10_* files for each format
   - Follow same interface pattern
   - Automatic integration into system

---

## Database Schema - No Changes Needed!

Current schema already supports this approach:
```sql
questions (
    question_id TEXT PRIMARY KEY,
    passage_id TEXT NOT NULL,
    question_text TEXT NOT NULL,
    question_type TEXT,              -- Can be deprecated/removed later
    answer_musicxml TEXT,
    answer_abc TEXT,
    answer_mei TEXT,
    answer_humdrum TEXT,
    verified_musicxml BOOLEAN DEFAULT 0,
    verified_abc BOOLEAN DEFAULT 0,
    verified_mei BOOLEAN DEFAULT 0,
    verified_humdrum BOOLEAN DEFAULT 0,
    FOREIGN KEY (passage_id) REFERENCES passages(passage_id)
)
```

**Migration Plan**:
1. ✅ Keep existing manual answers as validation dataset
2. ✅ Populate answer columns with programmatic extraction
3. ✅ Set `verified_*` flags to 1 when programmatic matches manual
4. ✅ Set `verified_*` flags to 0 when discrepancy found (needs human review)
5. ⏳ Optional: Drop `question_type` column after migration

---

## Answer Normalization Standards

### Pitch Notation
- **Format**: `{Note}{Accidental}{Octave}` (e.g., `C#5`, `Bb3`, `F4`)
- **Accidentals**: Use `#` for sharp, `b` for flat (ASCII-safe)
- **Octave**: Scientific pitch notation (C4 = middle C)
- **Enharmonics**: Preserve as written in score (don't convert Db to C#)

### Duration Notation
- **Beats**: Decimal numbers (e.g., `1`, `1.5`, `0.25`, `2.5`)
- **Named durations**: Title case (e.g., `Quarter note`, `Dotted eighth note`, `Sixteenth note`)
- **Consistency**: Same duration → same name across all formats

### Count Notation
- **Format**: Plain integer as string (e.g., `"16"`, `"3"`, `"0"`)
- **No units**: Just the number

### Interval Notation
- **Semitones**: Plain integer (e.g., `"7"`, `"12"`, `"1"`)
- **Named intervals**: If needed later (e.g., `"Perfect fifth"`)

---

## Edge Case Handling

### 1. **Tie Handling**
- **Rule**: Count tied notes only once
- **Implementation**: Check `tied_from_previous` / `<tie type="stop">` / etc.
- **Edge case**: Tie crosses measure boundary → flag for verification

### 2. **Grace Notes**
- **Rule**: Include grace notes and ornaments in counts
- **Implementation**: Detect grace notes in format-specific way
- **Edge case**: Complex ornaments → flag for verification

### 3. **Multi-voice/Hand Detection**
- **MusicXML**: Use `<staff>` element (staff 1 = right, staff 2 = left)
- **MEI**: Use `<staff>` element similarly
- **ABC**: Use `V:1` and `V:2` voice labels
- **Humdrum**: Use spine position (left spines = left hand typically)
- **Edge case**: Three or more staves → flag for verification

### 4. **Missing Measures**
- **Rule**: All passages should exist in all 4 formats (per your spec)
- **Implementation**: If measure range not found → raise ExtractionError
- **Edge case**: Measure numbering differs across formats → flag for verification

### 5. **Partial Measures**
- **Rule**: Count everything within the measure range
- **Edge case**: Pickup measures → flag for verification

---

## Validation & Error Handling

### Validation Report Format
```
VALIDATION REPORT
==================
Passage: P-024 (Sonata 16, Movement 1, Measures 1-1)
Question: Q-001 "How many notes are in the left hand..."

Format      | Programmatic | Manual | Match | Status
------------|--------------|--------|-------|--------
MusicXML    | 8            | 8      | ✓     | PASS
ABC         | 8            | 8      | ✓     | PASS
MEI         | 8            | 8      | ✓     | PASS
Humdrum     | 8            | 8      | ✓     | PASS

Cross-format consistency: ✓ PASS (all formats agree)
```

### Error Types

**ExtractionError** - Hard failures:
```python
class ExtractionError(Exception):
    """Cannot extract answer from this format."""
    pass

# Examples:
# - File cannot be parsed
# - Measure range not found
# - Format is malformed
```

**ValidationWarning** - Needs human review:
```python
class ValidationWarning(Warning):
    """Answer extracted but needs verification."""
    pass

# Examples:
# - Programmatic answer differs from manual answer
# - Edge case detected (tie across boundary, etc.)
# - Cross-format inconsistency
```

### Verification Workflow
1. Run extractor
2. Compare to manual answer (if exists)
3. If mismatch → log ValidationWarning → flag for review
4. Human reviews flagged answers
5. Update manual answer OR fix extractor code
6. Re-run validation until all pass

---

## Performance Considerations

### For Movement-Level Analysis
- **Challenge**: Entire movement could be 500+ measures
- **Solution 1**: Stream processing - don't load entire score into memory
- **Solution 2**: Measure indexing - jump directly to measure range
- **Solution 3**: Caching - cache parsed representation for repeated queries

### For Batch Processing
- **Challenge**: 421 questions × 4 formats = 1,684 extractions
- **Solution**: Parallel processing with ProcessPoolExecutor
- **Target**: < 5 minutes for full database regeneration

---

## Testing Strategy

### 1. **Unit Tests** - Each extractor in isolation
```python
def test_musicxml_count_notes_left_hand_single_bar():
    answer = extract_answer(
        'fixtures/sonata16_mvmt1_m1.musicxml',
        start_measure=1,
        end_measure=1,
        hand='left'
    )
    assert answer == "8"
```

### 2. **Integration Tests** - Cross-format consistency
```python
def test_cross_format_consistency_count_notes():
    passage_id = 'P-024'
    files = {
        'musicxml': 'fixtures/P-024.musicxml',
        'abc': 'fixtures/P-024.abc',
        'mei': 'fixtures/P-024.mei',
        'humdrum': 'fixtures/P-024.krn'
    }
    
    answers = {}
    for fmt, file_path in files.items():
        extractor = get_extractor(fmt, 'Q01')
        answers[fmt] = extractor(file_path, 1, 1, hand='left')
    
    # All formats must agree
    assert len(set(answers.values())) == 1, f"Inconsistency: {answers}"
```

### 3. **Regression Tests** - Validate against manual answers
```python
def test_regression_all_manual_answers():
    conn = sqlite3.connect('benchmark.db')
    questions = conn.execute("""
        SELECT question_id, passage_id, answer_musicxml 
        FROM questions 
        WHERE answer_musicxml IS NOT NULL
    """).fetchall()
    
    mismatches = []
    for qid, pid, manual_answer in questions:
        programmatic_answer = generate_answer(qid, pid, 'musicxml')
        if programmatic_answer != manual_answer:
            mismatches.append((qid, pid, manual_answer, programmatic_answer))
    
    # Flag mismatches for review (don't fail test)
    if mismatches:
        write_validation_report(mismatches)
```

---

## Adding New Question Types - Example

**New Question**: "How many times do the two hands play simultaneously?"

### Step 1: Create extractor for each format

**`musicxml/Q10_simultaneous_hands.py`**:
```python
def extract_answer(file_path: str, start_measure: int, end_measure: int) -> str:
    """Count moments where both hands have notes at same time."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    simultaneous_count = 0
    
    for measure_num in range(start_measure, end_measure + 1):
        # Get all onset times in this measure for both hands
        left_onsets = get_note_onsets(root, measure_num, hand='left')
        right_onsets = get_note_onsets(root, measure_num, hand='right')
        
        # Find overlapping onsets
        overlaps = left_onsets.intersection(right_onsets)
        simultaneous_count += len(overlaps)
    
    return str(simultaneous_count)
```

### Step 2: Implement for all other formats
- Create `abc/Q10_simultaneous_hands.py`
- Create `mei/Q10_simultaneous_hands.py`  
- Create `humdrum/Q10_simultaneous_hands.py`

### Step 3: Test
- Add unit tests for each format
- Add cross-format consistency test
- Validate on sample passages

### Step 4: Deploy
- Run on all passages
- Populate database
- Question type is now available!

**Time to add new question type**: < 1 day (as designed)

---

## Success Metrics

### Accuracy
- ✅ 100% cross-format agreement for same passage
- ✅ >95% match with manual answers (initial validation)
- ✅ Human verification for remaining 5% discrepancies

### Performance
- ✅ Generate answers for 1,684 questions in < 5 minutes
- ✅ Single movement analysis (500 measures) in < 10 seconds per format

### Maintainability
- ✅ New question type added in < 1 day
- ✅ Clear error messages for debugging
- ✅ Comprehensive test coverage (>80%)

### Extensibility
- ✅ Support single bar to entire movement from day 1
- ✅ Easy to add format-specific optimizations
- ✅ No changes to core architecture for new question types

---

## Next Steps - Your Approval Needed

**Before I start coding, please confirm**:

1. ✅ **Architecture**: Format × Question matrix (36 scripts total for 9 questions)?
2. ✅ **No format conversion**: Native parsing for each format?
3. ✅ **Multi-measure from start**: Design for entire movements?
4. ✅ **Manual answers as validation**: Keep existing answers for testing?
5. ✅ **Normalization standards**: Pitch (`C#5`), Duration (`Quarter note`), etc.?
6. ✅ **Edge case handling**: Flag discrepancies for your review?

**Questions for you**:

1. **Priority format**: Which format should I implement first? (I suggest MusicXML as proof of concept)
2. **Test passages**: Should I use your existing passages as fixtures, or create new test cases?
3. **Validation threshold**: What mismatch percentage is acceptable for initial validation? (I suggested 5%)
4. **Error handling**: Should extraction failures block the whole batch, or skip and flag?

Let me know if this revised plan meets your requirements, and I'll start building!

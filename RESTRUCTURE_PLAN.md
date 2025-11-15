# Repo Restructuring Plan

## Goal
Transition from manual verification to automated answer generation using format-specific parsers.

## Test Data Preserved
✓ Exported 72 verified Humdrum answers to `tests/verified_answers_humdrum.json`
✓ Created question type summary in `tests/question_type_summary.json`

## Core Question Types to Support (9 categories)

1. **Note counting - Left hand** (8 test cases)
   - "How many notes are in the left hand in this measure?"
   
2. **Note counting - Right hand** (8 test cases)
   - "How many notes are in the right hand in this measure?"
   
3. **Rest counting** (8 test cases)
   - "How many rests are in this measure?"
   
4. **Pitch class counting** (8 test cases)
   - "How many different pitch classes are used in the left hand?"
   
5. **Pitch identification - Lowest left hand** (8 test cases)
   - "What is the pitch of the lowest note in the left hand?"
   
6. **Pitch identification - First right hand** (7 test cases)
   - "What is the pitch of the first note in the right hand?"
   
7. **Duration - Longest note** (8 test cases)
   - "What is the duration of the longest note in this measure?"
   
8. **Duration - First note left hand** (8 test cases)
   - "What is the duration of the first note in the left hand?"
   
9. **Interval calculation** (7 test cases)
   - "What is the interval between the first and last notes in the right hand?"

## Cleanup Tasks

### Delete:
- [x] `data/question_passages_abc/`
- [x] `data/question_passages_musicxml/`
- [x] `outputs/passages_for_review/`
- [x] Move all `outputs/*` (except archive) to `outputs/archive/`

### Delete unnecessary scripts:
- [x] `src/scripts/generate_passages_for_review.py`
- [x] `src/scripts/list_passages_to_review.py`
- [x] `src/scripts/review_progress.py`
- [x] `src/cli/review_passage.py`
- [x] `src/cli/review_format.py`
- [x] `src/cli/review_all_questions.py`

### Keep:
- [x] Source encoding files in `data/{abc,humdrum,mei,musicxml}/`
- [x] `src/core/extract_passage.py`
- [x] `src/core/db_utils.py`
- [x] `src/cli/run_benchmark.py`
- [x] `src/llm/` (for LLM evaluation)

## New Structure

```
MusicEncodingBenchmark/
├── data/
│   ├── abc/          ✓ (keep source files)
│   ├── humdrum/      ✓ (keep source files)
│   ├── mei/          ✓ (keep source files)
│   └── musicxml/     ✓ (keep source files)
│
├── src/
│   ├── parsers/      📦 NEW
│   │   ├── __init__.py
│   │   ├── base_parser.py          (abstract base class)
│   │   ├── humdrum_parser.py       (start here - we have tests!)
│   │   ├── musicxml_parser.py
│   │   ├── abc_parser.py
│   │   └── mei_parser.py
│   │
│   ├── core/
│   │   ├── extract_passage.py      ✓ (keep)
│   │   ├── db_utils.py             ✓ (keep, update)
│   │   └── question_dispatcher.py  📦 NEW (maps questions to parsers)
│   │
│   ├── cli/
│   │   ├── run_benchmark.py        ✓ (keep)
│   │   ├── generate_answers.py     📦 NEW (regenerate all answers)
│   │   └── add_question.py         ✓ (keep, update)
│   │
│   └── llm/          ✓ (keep for benchmark execution)
│
├── tests/
│   ├── verified_answers_humdrum.json   ✓ (created)
│   ├── question_type_summary.json      ✓ (created)
│   ├── test_humdrum_parser.py          📦 NEW
│   ├── test_musicxml_parser.py         📦 NEW
│   ├── test_abc_parser.py              📦 NEW
│   └── test_mei_parser.py              📦 NEW
│
└── outputs/
    └── archive/      (move all current outputs here)
```

## Database Changes

### Remove fields:
- `questions.question_type` (misleading)
- `questions.verified_musicxml`
- `questions.verified_abc`
- `questions.verified_mei`
- `questions.verified_humdrum`

### Add field (optional):
- `questions.question_type_id` (maps to question dispatcher)

### Keep fields:
- `questions.answer_musicxml`
- `questions.answer_abc`
- `questions.answer_mei`
- `questions.answer_humdrum`

## Parser Requirements

Each parser must implement these methods:

```python
class BaseParser:
    def count_notes(self, passage_text: str, hand: str, include_grace: bool = True) -> int
    def count_rests(self, passage_text: str) -> int
    def count_pitch_classes(self, passage_text: str, hand: str) -> int
    def get_first_pitch(self, passage_text: str, hand: str) -> str
    def get_lowest_pitch(self, passage_text: str, hand: str) -> str
    def get_highest_pitch(self, passage_text: str, hand: str) -> str
    def get_first_note_duration(self, passage_text: str, hand: str) -> str
    def get_longest_note_duration(self, passage_text: str) -> str
    def calculate_interval(self, passage_text: str, hand: str) -> int
```

## Implementation Order

1. ✅ Export test data
2. 🔄 Clean up directories and scripts
3. 📦 Create parser structure (base class)
4. 📦 Implement Humdrum parser (we have 72 test cases!)
5. 📦 Create test suite using verified answers
6. 📦 Implement other format parsers
7. 📦 Create question dispatcher
8. 📦 Update database schema
9. 📦 Create `generate_answers.py` CLI tool
10. 📦 Regenerate all answers

## Critical Parsing Rules

### All Formats:
- Count tied notes only once
- Include grace notes and ornaments in counts
- Handle invisible/hidden notes correctly (especially MusicXML)

### Humdrum-specific:
- Grace notes: tokens with 'q' suffix
- Ties: '[' starts tie, ']' ends tie
- Staff identification: need to distinguish LH (staff2) vs RH (staff1)

### MusicXML-specific:
- Watch for `<print-object>no</print-object>` (invisible notes)
- Grace notes: `<grace/>` element
- Ties: `<tie type="start|stop"/>`

### ABC-specific:
- Voice identification: `[V:1]` = RH, `[V:2]` = LH
- Grace notes: acciaccaturas `{ABC}` and appoggiaturas

### MEI-specific:
- Staff identification via `@staff` attribute
- Grace notes: `@grace` attribute
- Ties: `<tie>` elements

## Next Steps

Ready to proceed with cleanup?

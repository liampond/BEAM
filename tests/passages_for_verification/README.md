# Test Passages for Verification

This directory contains the 10 unique passages from the 72 verified Humdrum test cases, exported in all 4 formats.

## Passage Summary

| Passage ID | Sonata | Movement | Measures | Question IDs | Count |
|------------|--------|----------|----------|--------------|-------|
| P-001      | 1      | 1        | 87       | 1,2,3,4,5,6,7,8,9 | 9 |
| P-002      | 2      | 1        | 27       | 10,11,12,13,14,15,16 | 7 |
| P-003      | 3      | 1        | 85       | 17,18,19,20,21,22,23,24,25 | 9 |
| P-004      | 4      | 3        | 56       | 26,27,28,29,30,31,32,33,34 | 9 |
| P-005      | 5      | 3        | 95       | 35,36,37,38,39,40,41,42,43 | 9 |
| P-006      | 6      | 1        | 122      | 44,45,46,47,48,49,50,51,52 | 9 |
| P-007      | 7      | 1        | 79       | 53,54,55,56,57,58,59,60,61 | 9 |
| P-008      | 8      | 1        | 37       | 62,63,64,65,66,67,68,69,70 | 9 |
| P-047      | 16     | 1        | 1-4      | 420 | 1 |
| P-051      | 16     | 1        | 1-73     | 421 | 1 |

**Total:** 10 passages, 72 test cases

## Directory Structure

```
passages_for_verification/
├── humdrum/     # 10 .krn files
├── musicxml/    # 10 .xml files
├── abc/         # 10 .abc files
└── mei/         # 10 .mei files
```

## Question Types Covered

Each passage (except P-047 and P-051) tests 9 different question types:

1. **Left hand note count** - "How many notes are in the left hand?"
2. **Right hand note count** - "How many notes are in the right hand?"
3. **First pitch (RH)** - "What is the pitch of the first note in the right hand?"
4. **Lowest pitch (LH)** - "What is the pitch of the lowest note in the left hand?"
5. **Longest duration** - "What is the duration of the longest note?"
6. **Pitch classes (LH)** - "How many different pitch classes in left hand?"
7. **Interval (RH)** - "Interval between first and last notes in right hand?"
8. **Rest count** - "How many rests are in this measure?"
9. **First note duration (LH)** - "Duration of the first note in the left hand?"

## Verification Instructions

### For Each Format:

1. **Open passage in notation software** (MuseScore, Finale, Sibelius, etc.)
2. **For each question, manually verify the answer:**
   - Count notes carefully
   - Check pitch spellings (use sharps/flats as encoded)
   - Measure durations in quarter note beats
   - Count tied notes only once
   - Include grace notes and ornaments

3. **Create verified answer file:**
   - `verified_answers_musicxml.json`
   - `verified_answers_abc.json`
   - `verified_answers_mei.json`

### Answer Format

Use the same structure as `verified_answers_humdrum.json`:

```json
[
  {
    "question_id": "1",
    "passage_id": "P-001",
    "sonata_number": 1,
    "movement": 1,
    "kv_number": "279",
    "start_measure": 87,
    "end_measure": 87,
    "num_measures": 1,
    "question_text": "How many notes are in the left hand in this measure?...",
    "expected_answer": "16",
    "format": "musicxml"  // or "abc" or "mei"
  },
  ...
]
```

## Important Notes

- **Encoding differences:** Different formats may encode the same music slightly differently (e.g., enharmonic spellings, ornament notation)
- **Invisible notes:** MusicXML may have hidden notes that shouldn't be counted
- **Voice/staff assignment:** Verify which voice/staff corresponds to left vs right hand
- **Ties:** Must handle ties across barlines correctly
- **Grace notes:** Should be included in counts

## Testing Workflow

1. Verify answers for **MusicXML** first (most structured format)
2. Then **MEI** (similar to MusicXML)
3. Then **ABC** (simplest but needs careful parsing)
4. Use verified answers to create test suites for each parser
5. Build parsers with 100% test pass rate before moving to next format

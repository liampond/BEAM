# Database Schema Changes - Passage Measure Mapping

## Summary

Successfully restructured the database to:
1. Use TEXT passage IDs (P-001, P-002, etc.) instead of INTEGER
2. Create separate `passage_measures` table for format-specific measure ranges
3. Support per-format verification tracking

## New Schema

### passages table
```sql
CREATE TABLE passages (
    passage_id TEXT PRIMARY KEY,           -- Changed from INTEGER to TEXT (P-001 format)
    piece_id INTEGER NOT NULL,
    granularity TEXT,
    start_measure INTEGER,                 -- Generic/reference measure number
    end_measure INTEGER,                   -- Generic/reference measure number
    description TEXT,
    num_measures INTEGER,
    FOREIGN KEY (piece_id) REFERENCES pieces(piece_id)
);
```

### passage_measures table (NEW)
```sql
CREATE TABLE passage_measures (
    passage_id TEXT NOT NULL,
    format TEXT NOT NULL,                  -- 'musicxml', 'abc', 'mei', 'humdrum'
    start_measure INTEGER NOT NULL,        -- Format-specific start measure
    end_measure INTEGER NOT NULL,          -- Format-specific end measure
    verified BOOLEAN DEFAULT 0,            -- Has this mapping been manually verified?
    notes TEXT,                            -- Optional notes about this mapping
    PRIMARY KEY (passage_id, format),
    FOREIGN KEY (passage_id) REFERENCES passages(passage_id)
);
```

### questions table
```sql
CREATE TABLE questions (
    question_id TEXT PRIMARY KEY,          -- Already TEXT (Q001 format)
    passage_id TEXT NOT NULL,              -- Changed from INTEGER to TEXT
    question_text TEXT NOT NULL,
    question_type TEXT,
    answer_musicxml TEXT,
    answer_abc TEXT,
    answer_mei TEXT,
    answer_humdrum TEXT,
    FOREIGN KEY (passage_id) REFERENCES passages(passage_id)
);
```

## Benefits

1. **Cleaner schema**: Core passage info separate from format-specific details
2. **Flexibility**: Easy to add new formats without altering tables
3. **Verification tracking**: `verified` flag tracks which mappings have been checked
4. **Optional data**: Not all passages need all formats
5. **Descriptive IDs**: P-004 is more readable than integer 4

## Current State

- All 50 passages migrated with IDs P-001 through P-050
- 200 passage_measures entries (50 passages × 4 formats)
- All currently have same measure numbers (initialized from generic measures)
- All verified=0 (need manual verification)

## Example: Passage P-004

**passages table:**
- passage_id: P-004
- piece_id: 12 (Sonata 04, Movement 3)
- start_measure: 56
- end_measure: 56
- description: K.282, Mvmt 3, m.56

**passage_measures table:**
- P-004, musicxml: 56-56 (verified=0)  ← INCORRECT, needs fixing
- P-004, abc: 56-56 (verified=0)
- P-004, mei: 56-56 (verified=0)
- P-004, humdrum: 56-56 (verified=0)  ← CORRECT

## Next Steps

1. Use Humdrum as the authoritative source (correct measure numbering)
2. Manually verify and update MusicXML measure numbers where they differ
3. Set `verified=1` after checking each format
4. Add notes about discrepancies in the `notes` column

## Usage

**Query format-specific measures:**
```sql
SELECT pm.format, pm.start_measure, pm.end_measure, pm.verified
FROM passage_measures pm
WHERE pm.passage_id = 'P-004'
ORDER BY pm.format;
```

**Update format-specific measures:**
```sql
UPDATE passage_measures
SET start_measure = 55, end_measure = 55, verified = 1, 
    notes = 'MusicXML counts pickup as measure 40, actual music is at 55'
WHERE passage_id = 'P-004' AND format = 'musicxml';
```

**Review passage with CLI:**
```bash
PYTHONPATH=src .venv/bin/python src/cli/review_passage.py P-004 humdrum
```

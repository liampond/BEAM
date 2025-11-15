# Core Modules

## passage_matcher.py

Automated content-based matching of musical passages across different encoding formats.

### Purpose

Solves the problem of **different measure numbering** across music encoding formats. When the same piece of music is encoded in Humdrum, ABC, MusicXML, and MEI, the measure numbers may not align due to:
- Different handling of repeats
- Pick-up measures
- Encoding conventions

### How It Works

1. **Extract Reference**: Reads a Humdrum passage and extracts a musical "signature":
   - Pitch sequence (MIDI note numbers)
   - Right hand vs left hand separation
   - Chord counts
   - Melodic intervals

2. **Search Nearby**: For each target format (ABC, MusicXML, MEI):
   - Searches ±10 measures around the Humdrum measure number
   - Extracts signatures for candidate passages
   - Compares using fuzzy matching

3. **Fuzzy Matching**: Accounts for encoding differences:
   - Key signature representation (ABC doesn't include key in pitch encoding)
   - Intervallic matching (relative pitches, not absolute)
   - Tolerant of small differences in note counts, chord counts

### Usage

```python
from pathlib import Path
from src.core.passage_matcher import find_passage_in_all_formats

results = find_passage_in_all_formats(
    humdrum_file=Path('data/humdrum/04-3.krn'),
    abc_file=Path('data/abc/04-3.abc'),
    musicxml_file=Path('data/musicxml/04-3.xml'),
    mei_file=Path('data/mei/04-3.mei'),
    humdrum_start=56,
    humdrum_end=56
)

# Returns: {'humdrum': (56, 56), 'abc': (58, 58), 'musicxml': (57, 57), 'mei': (56, 56)}
```

### Configuration

Customize matching behavior with `MatchingConfig`:

```python
from src.core.passage_matcher import MatchingConfig

config = MatchingConfig(
    search_window=15,  # Search ±15 measures (default: 10)
    note_count_tolerance=5,  # Allow ±5 notes difference (default: 3)
    interval_tolerance=2,  # Allow ±2 semitones per interval (default: 1)
    chord_count_tolerance=3,  # Allow ±3 chord difference (default: 2)
)
```

### Limitations

- **Key Signatures**: ABC pitch extraction doesn't currently parse key signatures, so it relies on interval matching
- **Complex Repeats**: Files with highly complex repeat structures may not match
- **Encoding Errors**: If source files have errors, matching will fail
- **Grace Notes**: Grace notes and ornaments may cause slight mismatches

### Known Issues

Some passages don't match across all formats:
- **P-003, P-005, P-008 in ABC**: These may have different repeat structures or encoding issues
- **P-002, P-047, P-008 in MusicXML/MEI**: Needs investigation

## extract_passage.py

Extracts specific measures from music encoding files with full headers and metadata.

### Supported Formats

- **Humdrum** (.krn): Extracts with all reference records and interpretations
- **ABC** (.abc): Extracts with complete header
- **MusicXML** (.xml): Extracts with part-list and attributes
- **MEI** (.mei): Extracts with scoreDef and section structure

### Usage

```python
from src.core.extract_passage import extract

content = extract(
    format='abc',
    file_path='data/abc/04-3.abc',
    start_measure=58,
    end_measure=58
)
```

## db_utils.py

Database utilities for querying and managing benchmark data.

---

## Development Notes

### Testing the Matcher

```bash
# Test a specific passage
python -c "
from pathlib import Path
from src.core.passage_matcher import find_passage_in_all_formats

result = find_passage_in_all_formats(
    humdrum_file=Path('data/humdrum/01-1.krn'),
    abc_file=Path('data/abc/01-1.abc'),
    musicxml_file=Path('data/musicxml/01-1.xml'),
    mei_file=Path('data/mei/01-1.mei'),
    humdrum_start=87,
    humdrum_end=87
)
print(result)
"
```

### Debugging Match Failures

If a passage isn't matching:

1. **Check signatures**:
   ```python
   from src.core.passage_matcher import PassageMatcher
   matcher = PassageMatcher(Path('data/humdrum/XX-Y.krn'), M, M)
   print(matcher.reference_signature)
   ```

2. **Inspect candidate measures**:
   Use `find_matching_measures.py` helper script to compare content

3. **Adjust tolerances**:
   Increase `search_window` or other tolerances in `MatchingConfig`

### Future Improvements

- [ ] Add key signature awareness to ABC pitch extraction
- [ ] Support for more complex repeat structures
- [ ] Caching of extracted signatures for performance
- [ ] Better handling of grace notes and ornaments
- [ ] Visualization of matching confidence scores

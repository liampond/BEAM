# Extract Passage Module - Refactoring Summary

## Overview
Successfully refactored `src/extract_passage.py` from a CLI-only tool to a dual-purpose module that supports both:
1. **Library usage** - For programmatic extraction by benchmark runner
2. **CLI usage** - For manual testing and inspection

## Key Changes

### 1. Library Interface
```python
from src.extract_passage import extract

content = extract(
    format="mei",              # One of: 'abc', 'mei', 'musicxml', 'humdrum'
    file_path="data/mei/16-1.mei",
    start_measure=1,
    end_measure=4
)
# Returns: String containing the extracted passage with all metadata
```

### 2. ABC Extraction Bug Fix
**Problem:** ABC extraction was returning ~9-10 measures instead of 4
- **Root Cause:** Used `body_lines[:20]` (first 20 lines)
- **Issue:** ABC has 2 voices per measure (V:1 and V:2), so 20 lines ≈ 10 measures
- **Solution:** Implemented proper measure counting by tracking Voice 1 lines with bar markers

**Fixed Algorithm:**
```python
current_measure = 0
for line in body_lines:
    if line.startswith('[V:1]'):
        if '|' in line:
            current_measure += 1
        if start_measure <= current_measure <= end_measure:
            extracted_lines.append(line)
    elif line.startswith('[V:2]'):
        if start_measure <= current_measure <= end_measure:
            extracted_lines.append(line)
```

### 3. Format-Specific Extractors
All extractors now return strings instead of printing/saving directly:
- `extract_abc(file_path, start_measure, end_measure) -> str`
- `extract_mei(file_path, start_measure, end_measure) -> str`
- `extract_musicxml(file_path, start_measure, end_measure) -> str`
- `extract_humdrum(file_path, start_measure, end_measure) -> str`

### 4. CLI Wrapper
Separate `cli_extract_and_display()` function handles:
- Display to console (truncated if > 2000 chars)
- Saving to file (with measure count verification)
- Error handling and user feedback

## Testing Results

### Verified All Formats Extract Exactly 4 Measures
```bash
python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4
```

**Results:**
- ✅ ABC: 4 measures (8 voice lines with bar markers)
- ✅ MEI: 4 `<measure>` elements
- ✅ MusicXML: 4 `<measure>` elements  
- ✅ Humdrum: 4 measure markers (=1- through =4)

### Test Files Updated
- `tests/test_abc.abc` - Replaced with correctly extracted 4 measures
- `tests/test_mei.mei` - Verified correct (4 measures)
- `tests/test_musicxml.xml` - Verified correct (4 measures)
- `tests/test_humdrum.krn` - Verified correct (4 measures)

## Integration with Benchmark Workflow

This refactoring supports the **Option A** workflow decided earlier:
1. User creates question with `create_question(sonata, movement, measures, question, answer)`
2. Function creates passage entry in database (stores metadata, not file content)
3. At benchmark runtime, `benchmark_runner.py` calls `extract()` for each format
4. Extracted content sent to LLM API
5. No pre-generated files needed

### Example Usage in Future benchmark_runner.py
```python
from src.extract_passage import extract
import sqlite3

def run_benchmark(question_id, llm_model):
    # Get passage info from database
    conn = sqlite3.connect('benchmark.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sonata_id, movement, start_measure, end_measure
        FROM passages WHERE id = ?
    ''', (question_id,))
    passage = cursor.fetchone()
    
    # Extract content for each format
    for format in ['abc', 'mei', 'musicxml', 'humdrum']:
        file_path = f"data/{format}/{passage[0]:02d}-{passage[1]}.{format}"
        content = extract(format, file_path, passage[2], passage[3])
        
        # Send to LLM API
        response = llm_api_call(content, question)
        
        # Store result in database
        # ...
```

## CLI Examples

### Extract all formats (display to console)
```bash
python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4
```

### Extract specific format and save to file
```bash
python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4 --format abc --output excerpt.abc
```

### Extract single measure
```bash
python src/extract_passage.py --sonata 16 --movement 1 --measures 5 --format mei
```

## Next Steps

1. **Add create_question() to db_utils.py**
   - Simple interface: `create_question(sonata, movement, measures, question_text, answer, granularity)`
   - Automatically creates passage if it doesn't exist
   - Creates question entry
   - Creates test_cases for all 4 formats

2. **Create benchmark_runner.py**
   - `run_benchmark(question_id, llm_model)` - Tests single question
   - `run_all_benchmarks(llm_model)` - Tests all questions
   - Integrates with `extract()` for on-demand content retrieval

3. **Add Sample Questions**
   - Use new workflow to add example questions at different granularities
   - Test end-to-end process

## Files Modified
- `src/extract_passage.py` - Completely refactored with bug fix
- `tests/test_abc.abc` - Updated with correctly extracted 4 measures

## Files Removed
- `src/extract_passage_old.py` - Backup file cleaned up

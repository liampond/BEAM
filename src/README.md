# Source Code

This directory contains the Music Encoding Benchmark implementation, organized by functional area.

## Directory Structure

```
src/
├── cli/              # Command-line interface tools
├── core/             # Core utilities and database access
├── llm/              # LLM integration and evaluation
├── scripts/          # Setup and maintenance scripts
└── README.md
```

## CLI Tools (`cli/`)

User-facing command-line tools for working with the benchmark.

### add_question.py
Simplified interface for adding questions to the benchmark database.

**Interactive Mode**:
```bash
python src/cli/add_question.py interactive
```

**Library Usage**:
```python
import sys
sys.path.insert(0, 'src')
from cli.add_question import create_question

create_question(
    sonata_number=16, 
    movement=1,
    start_measure=1, 
    end_measure=1,
    question_text="How many notes are in the left hand?",
    correct_answer="8",
    granularity="bar",      # bar, phrase, section, movement
    difficulty="easy",      # easy, medium, hard
    question_type="rhythmic" # general, harmonic, melodic, rhythmic, formal
)
```

### benchmark_runner.py
Orchestrates LLM benchmark testing: fetches test cases, extracts passages, sends to LLM providers, and evaluates responses.

**Usage**:
```bash
python src/cli/benchmark_runner.py --provider openai --question-id 1
```

## Core Utilities (`core/`)

Foundational modules used throughout the codebase.

### db_utils.py
Database helper functions for working with the benchmark database.

**Usage**:
```python
import sys
sys.path.insert(0, 'src')
from core.db_utils import get_piece_id, get_or_create_passage, add_question, create_test_cases
from core.db_utils import list_passages, list_questions, show_stats

# Get statistics
show_stats()

# List all passages and questions
list_passages()
list_questions()
```

### extract_passage.py
Extracts specific measures from music files. Can be used as a library or CLI tool.

**CLI Usage**:
```bash
# Extract measures 1-4 from Sonata 16, Movement 1 (all formats)
python src/core/extract_passage.py --sonata 16 --movement 1 --measures 1-4

# Extract specific format only
python src/core/extract_passage.py --sonata 16 --movement 1 --measures 1-4 --format mei
```

**Library Usage**:
```python
import sys
sys.path.insert(0, 'src')
from core.extract_passage import extract

# Returns dict with format keys and extracted content
passages = extract(sonata=16, movement=1, start_measure=1, end_measure=4)
abc_content = passages['abc']
```

## LLM Integration (`llm/`)

Components for testing LLM providers against the benchmark.

### runner.py
Lightweight LLM integration utilities: prompt builder, test case fetching, and response persistence.

### evaluator.py
Response evaluation with multiple strategies: exact match, fuzzy matching, regex, and numeric tolerance.

### integration/
LLM provider framework with abstraction layer for different backends (OpenAI, Anthropic, etc.).

## Scripts (`scripts/`)

Database initialization and maintenance utilities.

### init_database.py
Initializes the SQLite benchmark database with schema and metadata for all Mozart piano sonatas.

**Output**: `../benchmark.db` (SQLite database)

```bash
python src/scripts/init_database.py
```

Creates tables for:
- Pieces (46 active movements from sonatas 1-14, 16, 18)
- Encodings (4 formats per piece: ABC, MEI, MusicXML, Humdrum)
- Passages (musical excerpts for testing)
- Questions (benchmark questions with ground truth)
- Test cases (links questions to specific encodings)
- LLM responses (test results)

### generate_questions.py
Batch question generator with pre-verified questions.

```bash
# Interactive mode (review each question before adding)
python src/scripts/generate_questions.py

# Auto mode (add all questions without prompting)
python src/scripts/generate_questions.py auto
```

### cleanup_duplicate_questions.py
Database maintenance script to remove duplicate questions.

```bash
python src/scripts/cleanup_duplicate_questions.py
```

### data_import/
Scripts used to initially populate the `data/` directory:
- `import_abc.py` - Download and split ABC file from IFDO
- `import_mei.py` - Download MEI files from DME
- `import_musicxml.py` - Download MusicXML from DCMLab

## File Naming Convention

Music files in `../data/` use the format:
- `<sonata_number>-<movement>[variation_letter].<extension>`
- Examples: `01-1.mei`, `11-1a.abc`, `06-3m.krn`

## File Naming Convention

Music files in `../data/` use the format:
- `<sonata_number>-<movement>[variation_letter].<extension>`
- Examples: `01-1.mei`, `11-1a.abc`, `06-3m.krn`

## Current Status

- **46 pieces** indexed (Sonatas 1-14, 16, 18 with all movements)
- **184 encodings** (46 pieces × 4 formats)
- **4 passages** defined
- **19 questions** created (all "easy" difficulty, 1-bar granularity)
- **76 test cases** (19 questions × 4 formats)

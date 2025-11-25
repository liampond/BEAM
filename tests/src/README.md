# Source Code

This directory contains the Music Encoding Benchmark implementation, organized by functional area.

## Directory Structure

```
src/
├── cli/              # Command-line interface tools
│   ├── run_benchmark.py  # Main benchmark runner (uses config.yaml)
│   └── add_question.py   # Add questions to database
├── core/             # Core utilities and database access
│   ├── db_utils.py       # Database helper functions
│   └── extract_passage.py # Music excerpt extraction
├── llm/              # LLM integration and evaluation
│   ├── runner.py         # LLM interaction utilities
│   ├── evaluator.py      # Response evaluation
│   └── integration/      # Provider implementations
│       └── base.py       # Base classes & API wrappers
└── scripts/          # Setup and maintenance scripts
    └── database/         # Database management
        ├── init_database.py     # Database initialization
        └── export_database.py   # CSV export with stats
```

## CLI Tools (`cli/`)

User-facing command-line tools for working with the benchmark.

### run_benchmark.py (Main Entry Point)

The primary benchmark runner that uses `config.yaml` for configuration.

**Usage**:
```bash
# Run with default settings (all enabled models from config.yaml)
python src/cli/run_benchmark.py

# Run specific questions
python src/cli/run_benchmark.py --questions 22 23 24

# Run all questions
python src/cli/run_benchmark.py --all

# Test specific models only (overrides config)
python src/cli/run_benchmark.py --questions 22 --models qwen3-max claude-sonnet-4-5

# Use custom config file
python src/cli/run_benchmark.py --config my_config.yaml
```

**Configuration**: Edit `config.yaml` in the project root to:
- Enable/disable models
- Set API parameters (temperature, max_tokens, timeout)
- Configure output settings
- Choose evaluation strategies

**API Keys**: Stored in `.env` file (see `.env.example` for template)

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

## Core Utilities (`core/`)

Foundational modules used throughout the codebase.

### db_utils.py
Database helper functions for working with the benchmark database.

**Usage**:
```python
import sys
sys.path.insert(0, 'src')
from core.db_utils import get_piece_id, get_or_create_passage, add_question
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

### database/init_database.py
Initializes the SQLite benchmark database with the 4-table schema.

**Output**: `../../../benchmark.db` (SQLite database)

```bash
python src/scripts/database/init_database.py
```

Creates tables for:
- **question_types**: 9 question templates
- **passages**: 45 passages with verified measure ranges
- **questions**: 405 question instances (9 types × 45 passages)
- **llm_responses**: LLM evaluation results

### database/export_database.py
Exports all database tables to CSV files with statistics.

**Output**: `../../../database_exports/` directory

```bash
python src/scripts/database/export_database.py
```

Exports:
- `question_types.csv`
- `passages.csv`
- `questions.csv`
- `llm_responses.csv`
- `database_summary.txt` (statistics)

## File Naming Convention

Music files in `../data/` use the format:
- `<sonata_number>-<movement>[variation_letter].<extension>`
- Examples: `01-1.mei`, `11-1a.abc`, `06-3m.krn`

## Current Status

- **9 question types**: Covering pitch, rhythm, counting, intervals, etc.
- **45 passages**: From Sonatas 1-14, 16, 18
- **405 questions**: 9 types × 45 passages
- **88 verified answers per format**: Manually verified for ABC, Humdrum, MEI, MusicXML

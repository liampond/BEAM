# Scripts Directory

Utility scripts for database management, data import, and validation.

## Directory Structure

### `database/` - Database Management Scripts

- **`init_database.py`** - Initialize a new benchmark database with schema
- **`view_database.py`** - View and export database contents in various formats (CSV, Markdown, terminal)
- **`migrate_database_v2.py`** - Database migration script (adds format-specific answer columns, renumbers passages/questions)
- **`create_missing_test_cases.py`** - Generate test cases for questions that don't have them

### `data_import/` - Data Import Utilities

- **`import_musicxml.py`** - Import MusicXML files into the encodings table
- **`import_abc.py`** - Import ABC notation files into the encodings table
- **`import_mei.py`** - Import MEI files into the encodings table

### `validation/` - One-Time Validation Scripts

Scripts used for data validation and migration verification. These were used during development but may not be needed regularly:

- **`validate_all_answers_cross_format.py`** - Cross-format answer validation
- **`validate_rest_counts_cross_format.py`** - Compare rest counts across different encoding formats

### Root Scripts

- **`list_passages_to_review.py`** - List passages that need manual review
- **`regenerate_format_answers.py`** - Regenerate format-specific answers from MusicXML analysis

## Usage Examples

### View Database

```bash
# View in terminal (first 20 questions, without answers)
PYTHONPATH=src python src/scripts/database/view_database.py --limit 20 --no-answers

# Export to Markdown
PYTHONPATH=src python src/scripts/database/view_database.py --export md --output outputs/database.md

# Export to CSV
PYTHONPATH=src python src/scripts/database/view_database.py --export csv

# View specific passage
PYTHONPATH=src python src/scripts/database/view_database.py --passage 5
```

### Initialize Database

```bash
PYTHONPATH=src python src/scripts/database/init_database.py
```

### Import Data

```bash
# Import MusicXML files
PYTHONPATH=src python src/scripts/data_import/import_musicxml.py

# Import ABC files
PYTHONPATH=src python src/scripts/data_import/import_abc.py
```

## Notes

- All scripts should be run from the repository root with `PYTHONPATH=src`
- Database scripts operate on `benchmark.db` by default
- Backups are automatically created before migrations

# Scripts Directory

Utility scripts for database management and data import.

## Directory Structure

### `database/` - Database Management Scripts

- **`init_database.py`** - Initialize a new benchmark database with 4-table schema
- **`export_database.py`** - Export database tables to CSV with statistics

## Usage Examples

### Initialize Database

```bash
python src/scripts/database/init_database.py
```

Creates `benchmark.db` with:
- **question_types**: 9 question templates
- **passages**: 45 passages with verified measure ranges
- **questions**: 405 question instances
- **llm_responses**: LLM evaluation results (empty initially)

### Export Database

```bash
python src/scripts/database/export_database.py
```

Creates `database_exports/` with:
- `question_types.csv`
- `passages.csv`
- `questions.csv`
- `llm_responses.csv`
- `database_summary.txt` (statistics)

## Notes

- All scripts should be run from the repository root
- Database scripts operate on `benchmark.db` by default
- Exports are gitignored and should not be committed

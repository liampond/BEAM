# Quick Start: Using the Benchmark Database

## What's Been Created

✅ **benchmark.db** - SQLite database with:
- 46 active pieces (movements from sonatas 1-14, 16, 18)
- 192 encoding entries (4 formats per piece)
- 1 example passage (Sonata 16, Movement 1, measures 1-4)
- Empty tables ready for your questions

✅ **Helper scripts**:
- `src/init_database.py` - Creates/resets the database
- `src/extract_passage.py` - View music excerpts
- `src/db_utils.py` - Convenience functions for database operations
- `src/example_add_questions.py` - Example workflow

## Quick Commands

### View Database Status
```bash
python src/db_utils.py stats
```

### List All Passages
```bash
python src/db_utils.py passages

# Filter by sonata
python src/db_utils.py passages 16

# Filter by sonata and movement
python src/db_utils.py passages 16 1
```

### List All Questions
```bash
python src/db_utils.py questions

# Filter by passage
python src/db_utils.py questions 1
```

### Extract Music for Inspection
```bash
# View measures from a specific format
python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4 --format mei

# View from all formats
python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4 --format all
```

## Adding Your First Question

### Method 1: Using Python (Recommended)

```python
from src.db_utils import add_passage, add_question, create_test_cases

# Add a passage (if not already exists)
passage_id = add_passage(
    sonata_number=16,
    movement=1,
    start_measure=1,
    end_measure=4,
    description="Opening theme",
    granularity="bar"
)

# Add a question
question_id = add_question(
    passage_id=passage_id,
    question_text="What is the time signature?",
    correct_answer="4/4",
    difficulty="easy",
    question_type="notation"
)

# Create test cases for all formats
create_test_cases(question_id)
```

### Method 2: Direct SQL

```bash
sqlite3 benchmark.db
```

```sql
-- Add a question
INSERT INTO questions (passage_id, question_text, correct_answer, difficulty, question_type)
VALUES (1, 'What is the time signature?', '4/4', 'easy', 'notation');

-- Get the question_id (should be 1 if first question)
SELECT last_insert_rowid();

-- Create test cases for all 4 formats
INSERT INTO test_cases (question_id, encoding_id)
SELECT 1, encoding_id FROM encodings WHERE piece_id = 
    (SELECT piece_id FROM pieces WHERE sonata_number = 16 AND movement = 1);

-- Verify
SELECT * FROM test_cases;
```

## Example Workflow

### 1. Examine the music
```bash
python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4 --format mei
```

### 2. Write your question and determine ground truth
Based on what you see, write:
- Question: "What is the first pitch in the right hand in measure 1?"
- Answer: "B4"

### 3. Add to database
```python
from src.db_utils import add_question, create_test_cases

q_id = add_question(
    passage_id=1,  # The example passage for Sonata 16-1, mm. 1-4
    question_text="What is the first pitch in the right hand in measure 1?",
    correct_answer="B4",
    difficulty="medium",
    question_type="pitch"
)

create_test_cases(q_id)
```

### 4. Verify
```bash
python src/db_utils.py questions
```

## Question Types to Consider

### Easy (Single fact)
- "What is the time signature?"
- "What is the key signature?"
- "What clef is used for the right hand?"

### Medium (Counting/single bar)
- "How many eighth notes are in measure 3?"
- "What is the first pitch in measure 2?"
- "What interval is between the first two notes in the melody?"

### Hard (Multiple bars/patterns)
- "How many times does the pitch C5 appear in measures 1-4?"
- "What is the rhythmic pattern in the left hand in measures 2-3?"
- "What is the highest pitch in the right hand in measures 1-4?"

## Next Steps

1. **Add more passages** for Sonata 16, Movement 1
2. **Write bar-level questions** with ground truth answers
3. **Test with one LLM** to see if the question format works
4. **Expand gradually** to other movements/sonatas
5. **Add phrase/section questions** later

## Notes

- Start small: Focus on Sonata 16, Movement 1 for now
- Questions must be objective (right/wrong, no subjectivity)
- Test with actual music excerpts to verify your ground truth
- Each question tests all 4 formats automatically via test_cases
- Run `python src/example_add_questions.py --run` to see example questions added

## Database Schema Reference

See `DATABASE.md` for complete documentation of all tables and fields.

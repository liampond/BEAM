# Benchmark Database Guide

## Overview

The LLM Music Encoding Benchmark tests which music notation formats are best understood by Large Language Models. This focuses on **objective, factual questions** about the music itself, not music theory analysis.

## Database Structure

### Tables

1. **pieces** - Individual movements from Mozart piano sonatas
   - `sonata_number`: 1-18 (common subset: 1-14, 16, 18)
   - `kv_number`: Köchel catalog number
   - `movement`: 1-3
   - `excluded`: Boolean (variation movements are excluded for now)

2. **encodings** - File references for each format
   - Links to `pieces`
   - `format`: abc, mei, musicxml, humdrum
   - `file_path`: Relative path to the encoding file

3. **passages** - Musical excerpts for testing
   - Links to `pieces`
   - `granularity`: bar, phrase, section, movement
   - `start_measure`, `end_measure`: Measure range
   - `description`: Human-readable description

4. **questions** - Benchmark questions
   - Links to `passages`
   - `question_text`: The actual question to ask the LLM
   - `correct_answer`: Ground truth answer
   - `difficulty`: easy, medium, hard
   - `question_type`: For categorization

5. **test_cases** - Links questions to specific encodings
   - Many-to-many relationship between questions and encodings
   - Each combination is a separate test case

6. **llm_responses** - Test results (populated when running benchmark)
   - Links to `test_cases`
   - `llm_model`: Which model was tested
   - `llm_response`: What the LLM answered
   - `is_correct`: Whether it matches ground truth
   - `response_time`: How long it took

## Current Status

- **46 active pieces** ready for benchmarking
- **2 excluded pieces** (variation movements: 06-3, 11-1)
- **192 encoding entries** (46 pieces × 4 formats)
- **1 example passage** created (Sonata 16, Movement 1, measures 1-4)
- **0 questions** (awaiting manual creation)

## Excluded Content

The following are currently excluded from benchmarking:
- **Sonata 15** (K.533) - Missing from ABC/Humdrum sources
- **Sonata 17** (K.570) - Missing from ABC/Humdrum sources
- **Sonata 06, Movement 3** - Variation movement (not standardized)
- **Sonata 11, Movement 1** - Variation movement (not standardized)

## Helper Scripts

### `init_database.py`
Creates the database schema and populates metadata.

```bash
python src/init_database.py
```

### `extract_passage.py`
Extracts specific measures from encoding files for inspection.

```bash
# Extract measures 1-4 from Sonata 16, Movement 1
python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4

# Extract from specific format
python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4 --format mei

# Extract all formats
python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4 --format all
```

## Question Writing Guidelines

### Objective Questions Only
- ✅ "What is the time signature in measure 5?"
- ✅ "How many eighth notes appear in measure 3?"
- ✅ "What pitch is the first note in measure 2?"
- ✅ "What is the key signature?"
- ❌ "Describe the harmonic progression" (subjective)
- ❌ "What emotion does this convey?" (subjective)
- ❌ "Is this a sonata form?" (analytical, not factual)

### Question Types to Consider
1. **Notation elements**: time signatures, key signatures, clefs
2. **Note counting**: how many notes of a specific duration
3. **Pitch identification**: what pitch appears at a specific location
4. **Interval identification**: what interval between two specific notes
5. **Rhythmic patterns**: does a specific rhythm appear
6. **Dynamics/articulation**: what marking appears at a location

### Difficulty Levels
- **Easy**: Single fact lookup (time signature, key)
- **Medium**: Counting or pattern matching within a bar
- **Hard**: Relationships across multiple bars

## Workflow for Adding Questions

1. **Choose a passage** (or create new one)
   ```sql
   SELECT * FROM passages;
   ```

2. **Extract the music** to inspect
   ```bash
   python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4
   ```

3. **Write question and determine ground truth** manually

4. **Insert into database**
   ```sql
   INSERT INTO questions (passage_id, question_text, correct_answer, difficulty, question_type)
   VALUES (1, 'What is the time signature?', '4/4', 'easy', 'notation');
   ```

5. **Create test cases** for each encoding format
   ```sql
   INSERT INTO test_cases (question_id, encoding_id)
   SELECT 1, encoding_id FROM encodings WHERE piece_id = 
       (SELECT piece_id FROM pieces WHERE sonata_number = 16 AND movement = 1);
   ```

## Example: First Question

For the example passage (Sonata 16, Movement 1, measures 1-4):

**Question**: "What is the time signature of this movement?"  
**Answer**: "4/4"  
**Difficulty**: easy  
**Type**: notation  

This question will be tested against all 4 encoding formats for this piece.

## Next Steps

1. Manually add more passages for Sonata 16, Movement 1
2. Write bar-level questions with ground truth
3. Build benchmark runner to test LLMs
4. Expand to other sonatas
5. Add phrase/section/movement level questions later

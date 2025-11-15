#!/usr/bin/env python3
"""
Generate test templates for manual verification of passages across all formats.

This script creates JSON templates for verifying answers in all formats at once.
It uses the PassageMatcher to automatically find format-specific measure numbers.

Usage:
    python generate_verification_tests.py
    
Output:
    tests/verification_templates/P-001_all_formats.json
    tests/verification_templates/P-002_all_formats.json
    ...
"""

import json
from pathlib import Path
from collections import defaultdict
from src.core.passage_matcher import find_passage_in_all_formats

# Load verified Humdrum answers
humdrum_file = Path('tests/verified_answers_humdrum.json')
with open(humdrum_file) as f:
    humdrum_answers = json.load(f)

# Group by passage_id
passages = defaultdict(list)
for item in humdrum_answers:
    passages[item['passage_id']].append(item)

# Create output directory
output_dir = Path('tests/verification_templates')
output_dir.mkdir(parents=True, exist_ok=True)

print("Generating verification test templates for all formats...\n")

for passage_id, questions in sorted(passages.items()):
    # Get passage metadata from first question
    first_q = questions[0]
    sonata_num = first_q['sonata_number']
    movement = first_q['movement']
    kv_number = first_q['kv_number']
    humdrum_start = first_q['start_measure']
    humdrum_end = first_q['end_measure']
    num_measures = first_q['num_measures']
    
    # Construct file paths
    humdrum_file = Path(f'data/humdrum/{sonata_num:02d}-{movement}.krn')
    abc_file = Path(f'data/abc/{sonata_num:02d}-{movement}.abc')
    musicxml_file = Path(f'data/musicxml/{sonata_num:02d}-{movement}.xml')
    mei_file = Path(f'data/mei/{sonata_num:02d}-{movement}.mei')
    
    # Check if files exist
    if not humdrum_file.exists():
        print(f"⚠️  {passage_id}: Humdrum file not found: {humdrum_file}")
        continue
    
    # Find matching measures in all formats
    print(f"Processing {passage_id} (K{kv_number}, mvt {movement}, measures {humdrum_start}-{humdrum_end})...")
    
    try:
        matches = find_passage_in_all_formats(
            humdrum_file=humdrum_file,
            abc_file=abc_file if abc_file.exists() else None,
            musicxml_file=musicxml_file if musicxml_file.exists() else None,
            mei_file=mei_file if mei_file.exists() else None,
            humdrum_start=humdrum_start,
            humdrum_end=humdrum_end
        )
    except Exception as e:
        print(f"  ❌ Error matching: {e}")
        matches = {'humdrum': (humdrum_start, humdrum_end)}
    
    # Display what was found
    format_status = []
    for fmt in ['humdrum', 'abc', 'musicxml', 'mei']:
        if fmt in matches:
            start, end = matches[fmt]
            format_status.append(f"{fmt}:{start}-{end}")
        else:
            format_status.append(f"{fmt}:NOT_FOUND")
    print(f"  Found: {', '.join(format_status)}")
    
    # Generate test template for all formats
    template = {
        "passage_id": passage_id,
        "metadata": {
            "sonata_number": sonata_num,
            "movement": movement,
            "kv_number": kv_number,
            "num_measures": num_measures,
            "description": f"K{kv_number} mvt {movement}"
        },
        "measures": {
            "humdrum": {"start": humdrum_start, "end": humdrum_end},
            "abc": {"start": matches['abc'][0], "end": matches['abc'][1]} if 'abc' in matches else None,
            "musicxml": {"start": matches['musicxml'][0], "end": matches['musicxml'][1]} if 'musicxml' in matches else None,
            "mei": {"start": matches['mei'][0], "end": matches['mei'][1]} if 'mei' in matches else None
        },
        "files": {
            "humdrum": f"{sonata_num:02d}-{movement}.krn",
            "abc": f"{sonata_num:02d}-{movement}.abc" if abc_file.exists() else None,
            "musicxml": f"{sonata_num:02d}-{movement}.xml" if musicxml_file.exists() else None,
            "mei": f"{sonata_num:02d}-{movement}.mei" if mei_file.exists() else None
        },
        "questions": []
    }
    
    # Add all questions for this passage
    for q in questions:
        question_template = {
            "question_id": q['question_id'],
            "question_text": q['question_text'],
            "answers": {
                "humdrum": q['expected_answer'],
                "abc": "VERIFY",  # To be filled in manually
                "musicxml": "VERIFY",  # To be filled in manually
                "mei": "VERIFY"  # To be filled in manually
            }
        }
        template['questions'].append(question_template)
    
    # Save template
    output_file = output_dir / f"{passage_id}_all_formats.json"
    with open(output_file, 'w') as f:
        json.dump(template, f, indent=2)
    
    print(f"  ✓ Saved template: {output_file}\n")

print(f"\n✓ Generated {len(passages)} verification templates")
print(f"  Location: {output_dir}/")
print("\nNext steps:")
print("1. Open each *_all_formats.json file")
print("2. For each question, verify the answer in ABC, MusicXML, and MEI")
print("3. Replace 'VERIFY' with the actual answer")
print("4. Run convert_templates_to_test_files.py to generate format-specific test files")

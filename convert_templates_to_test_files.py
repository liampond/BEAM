#!/usr/bin/env python3
"""
Convert verified templates to format-specific test files.

After manually verifying answers in the *_all_formats.json templates,
this script generates the format-specific JSON files for testing.

Usage:
    python convert_templates_to_test_files.py
    
Output:
    tests/verified_answers_abc.json
    tests/verified_answers_musicxml.json
    tests/verified_answers_mei.json
"""

import json
from pathlib import Path
from collections import defaultdict

# Load all template files
template_dir = Path('tests/verification_templates')
template_files = sorted(template_dir.glob('P-*_all_formats.json'))

if not template_files:
    print("❌ No template files found in tests/verification_templates/")
    print("   Run generate_verification_tests.py first")
    exit(1)

# Collect answers by format
format_answers = {
    'abc': [],
    'musicxml': [],
    'mei': []
}

print("Converting verification templates to test files...\n")

for template_file in template_files:
    with open(template_file) as f:
        template = json.load(f)
    
    passage_id = template['passage_id']
    metadata = template['metadata']
    measures = template['measures']
    files = template['files']
    
    verified_count = 0
    total_count = 0
    
    # Process each question
    for question in template['questions']:
        question_id = question['question_id']
        question_text = question['question_text']
        answers = question['answers']
        
        # Check each format
        for fmt in ['abc', 'musicxml', 'mei']:
            total_count += 1
            
            # Skip if format not available for this passage
            if measures[fmt] is None or files[fmt] is None:
                continue
            
            # Skip if answer not yet verified
            if answers[fmt] == 'VERIFY':
                continue
            
            # Add to format-specific answers
            verified_count += 1
            format_answers[fmt].append({
                "question_id": question_id,
                "passage_id": passage_id,
                "sonata_number": metadata['sonata_number'],
                "movement": metadata['movement'],
                "kv_number": metadata['kv_number'],
                "start_measure": measures[fmt]['start'],
                "end_measure": measures[fmt]['end'],
                "num_measures": metadata['num_measures'],
                "question_text": question_text,
                "expected_answer": answers[fmt],
                "format": fmt
            })
    
    status = "✓" if verified_count > 0 else "⚠️"
    print(f"{status} {passage_id}: {verified_count}/{total_count} answers verified")

print()

# Save format-specific files
for fmt, answers in format_answers.items():
    if not answers:
        print(f"⚠️  No verified answers for {fmt.upper()}")
        continue
    
    output_file = Path(f'tests/verified_answers_{fmt}.json')
    with open(output_file, 'w') as f:
        json.dump(answers, f, indent=2)
    
    print(f"✓ Saved {len(answers)} {fmt.upper()} answers to {output_file}")

print("\n" + "="*60)
print("Summary:")
print(f"  ABC:      {len(format_answers['abc'])} test cases")
print(f"  MusicXML: {len(format_answers['musicxml'])} test cases")
print(f"  MEI:      {len(format_answers['mei'])} test cases")
print("="*60)

#!/usr/bin/env python3
"""
View extracted passages for verification.

Usage:
    python view_passage.py P-001
    
Output:
    - Saves all formats to tests/passages_for_verification/{passage_id}/
    - Shows summary in terminal
"""

import sys
import json
from pathlib import Path
from src.core.extract_passage import extract

if len(sys.argv) < 2:
    print("Usage: python view_passage.py P-001")
    sys.exit(1)

passage_id = sys.argv[1]
template_file = Path(f'tests/verification_templates/{passage_id}_all_formats.json')

if not template_file.exists():
    print(f"❌ Template not found: {template_file}")
    sys.exit(1)

with open(template_file) as f:
    template = json.load(f)

# Create output directory
output_dir = Path(f'tests/passages_for_verification/{passage_id}')
output_dir.mkdir(parents=True, exist_ok=True)

print(f"\n{'='*80}")
print(f"Passage: {passage_id} - {template['metadata']['description']}")
print(f"{'='*80}\n")

saved_files = []

for fmt in ['humdrum', 'abc', 'musicxml', 'mei']:
    if template['measures'][fmt] is None:
        print(f"❌ {fmt.upper()}: NOT FOUND\n")
        continue
    
    measures = template['measures'][fmt]
    filename = template['files'][fmt]
    
    try:
        content = extract(
            format=fmt,
            file_path=f"data/{fmt}/{filename}",
            start_measure=measures['start'],
            end_measure=measures['end']
        )
        
        # Save all formats to files
        ext_map = {
            'humdrum': 'krn',
            'abc': 'abc',
            'musicxml': 'xml',
            'mei': 'mei'
        }
        output_file = output_dir / f'{passage_id}.{ext_map[fmt]}'
        with open(output_file, 'w') as f:
            f.write(content)
        
        saved_files.append((fmt.upper(), filename, f"{measures['start']}-{measures['end']}", output_file))
        print(f"✓ {fmt.upper()}: {filename}, measures {measures['start']}-{measures['end']}")
        print(f"  Saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ {fmt.upper()} Error: {e}")

print(f"\n{'='*80}")
print("Questions to verify:")
print(f"{'='*80}\n")

for i, q in enumerate(template['questions'], 1):
    print(f"{i}. Q{q['question_id']}: {q['question_text']}")
    print(f"   Humdrum answer: {q['answers']['humdrum']}")
    print()

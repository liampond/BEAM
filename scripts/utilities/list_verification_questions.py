#!/usr/bin/env python3
"""
Display questions for each passage to help with manual verification.
"""

import json
from collections import defaultdict

def main():
    # Load verified Humdrum test cases
    with open('tests/verified_answers_humdrum.json', 'r') as f:
        test_cases = json.load(f)
    
    # Group by passage_id
    passages = defaultdict(list)
    for tc in test_cases:
        passages[tc['passage_id']].append(tc)
    
    # Sort passages by ID
    for passage_id in sorted(passages.keys()):
        cases = passages[passage_id]
        first = cases[0]
        
        print(f"\n{'='*80}")
        print(f"PASSAGE: {passage_id}")
        print(f"Sonata {first['sonata_number']}, Movement {first['movement']}, "
              f"K.{first['kv_number']}, Measure(s) {first['start_measure']}-{first['end_measure']}")
        print(f"{'='*80}")
        
        for tc in sorted(cases, key=lambda x: int(x['question_id'])):
            print(f"\nQ-{tc['question_id']:>3}: {tc['question_text']}")
            print(f"        Answer: {tc['expected_answer']}")
        
        print()

if __name__ == '__main__':
    main()

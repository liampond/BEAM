#!/usr/bin/env python3
"""
Export all verified Humdrum passages to verified_passages/humdrum/
This creates a clean reference set of passages that we've manually verified.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.format_parsers.humdrum_parser import HumdrumParser


def main():
    print("="*70)
    print("EXPORTING VERIFIED HUMDRUM PASSAGES")
    print("="*70)
    
    # Load verified test cases
    verified_file = Path('tests/verified_answers_humdrum.json')
    with open(verified_file) as f:
        test_cases = json.load(f)
    
    # Get unique passages
    passages = {}
    for tc in test_cases:
        pid = tc['passage_id']
        if pid not in passages:
            passages[pid] = {
                'sonata': tc['sonata_number'],
                'movement': tc['movement'],
                'start': tc['start_measure'],
                'end': tc['end_measure'],
                'kv': tc['kv_number']
            }
    
    # Create output directory
    output_dir = Path('verified_passages/humdrum')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Export each passage
    parser = HumdrumParser()
    
    for pid in sorted(passages.keys(), key=lambda x: int(x.split('-')[1]) if '-' in x else 0):
        p = passages[pid]
        
        # Construct file path
        sonata = p['sonata']
        movement = p['movement']
        file_path = Path(f'data/humdrum/{sonata:02d}-{movement}.krn')
        
        if not file_path.exists():
            print(f"❌ {pid}: File not found: {file_path}")
            continue
        
        print(f"\n{pid}: Sonata {sonata}, Movement {movement}, K.{p['kv']}")
        print(f"  Source: {file_path.name}")
        print(f"  Measures: {p['start']}-{p['end']}")
        
        try:
            # Extract the passage
            sig = parser.extract_signature(
                file_path=file_path,
                start_measure=p['start'],
                end_measure=p['end']
            )
            
            if sig is None:
                print(f"  ❌ Parser returned None - could not extract")
                continue
            
            # Read the raw content from the file
            with open(file_path) as f:
                lines = f.readlines()
            
            # Find the measure range in the file
            in_range = False
            passage_lines = []
            measure_offset = parser._get_measure_offset(lines)
            target_start = p['start'] + measure_offset - 1
            target_end = p['end'] + measure_offset - 1
            
            # Collect header lines first
            for line in lines:
                if line.startswith('**'):
                    passage_lines.append(line)
                    break
            
            # Collect measure content
            for line in lines:
                if line.startswith('='):
                    # Extract measure number
                    measure_marker = line.split('\t')[0]
                    if measure_marker.startswith('='):
                        num_str = measure_marker[1:].rstrip('-').split()[0]
                        if num_str and num_str.isdigit():
                            measure_num = int(num_str)
                            if measure_num == target_start:
                                in_range = True
                            elif measure_num > target_end:
                                break
                
                if in_range:
                    passage_lines.append(line)
            
            # Add ending marker
            if passage_lines and not passage_lines[-1].startswith('=='):
                passage_lines.append('==\t==\t==\n')
            
            # Write to output file
            output_file = output_dir / f'{pid}.krn'
            with open(output_file, 'w') as f:
                f.writelines(passage_lines)
            
            print(f"  ✅ Exported: {output_file.name} ({sig.note_count} notes)")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print(f"✅ Export complete!")
    print(f"   Output directory: {output_dir}")
    print(f"   Total passages: {len(passages)}")
    print("\nThese passages are now available for:")
    print("  - Manual verification")
    print("  - Visual inspection in notation software")
    print("  - Reference comparison")


if __name__ == '__main__':
    main()

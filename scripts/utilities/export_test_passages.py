#!/usr/bin/env python3
"""
Export the 72 verified Humdrum passages in all 4 formats for verification.
Uses automated content matching to find corresponding measures in each format.
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from src.core.extract_passage import extract
from src.core.passage_matcher import find_passage_in_all_formats

def main():
    # Load verified Humdrum test cases to get unique passages
    with open('tests/verified_answers_humdrum.json', 'r') as f:
        test_cases = json.load(f)
    
    # Create output directories
    output_dir = Path('tests/passages_for_verification')
    for fmt in ['humdrum', 'musicxml', 'abc', 'mei']:
        (output_dir / fmt).mkdir(parents=True, exist_ok=True)
    
    print(f"Exporting passages in 4 formats using automated content matching...")
    print("="*70)
    
    # Get unique passages (avoid duplicates from multiple questions)
    seen_passages = set()
    
    for tc in test_cases:
        passage_id = tc['passage_id']
        
        # Skip if we already exported this passage
        if passage_id in seen_passages:
            continue
        seen_passages.add(passage_id)
        
        sonata_num = tc['sonata_number']
        movement = tc['movement']
        humdrum_start = tc['start_measure']
        humdrum_end = tc['end_measure']
        
        print(f"\n{passage_id}: Sonata {sonata_num}, Movement {movement}")
        print(f"  Humdrum source: measures {humdrum_start}-{humdrum_end}")
        
        # File paths
        humdrum_file = Path(f"data/humdrum/{sonata_num:02d}-{movement}.krn")
        abc_file = Path(f"data/abc/{sonata_num:02d}-{movement}.abc")
        musicxml_file = Path(f"data/musicxml/{sonata_num:02d}-{movement}.xml")
        mei_file = Path(f"data/mei/{sonata_num:02d}-{movement}.mei")
        
        # Find corresponding measures in all formats
        print("  Searching for matching content in other formats...")
        try:
            measure_map = find_passage_in_all_formats(
                humdrum_file=humdrum_file,
                abc_file=abc_file,
                musicxml_file=musicxml_file,
                mei_file=mei_file,
                humdrum_start=humdrum_start,
                humdrum_end=humdrum_end
            )
            
            print(f"  ✓ Found matches:")
            for fmt, (start, end) in measure_map.items():
                print(f"    - {fmt}: measures {start}-{end}")
            
        except Exception as e:
            print(f"  ❌ Error finding matches: {e}")
            # Fall back to using same measure numbers
            measure_map = {
                'humdrum': (humdrum_start, humdrum_end),
                'abc': (humdrum_start, humdrum_end),
                'musicxml': (humdrum_start, humdrum_end),
                'mei': (humdrum_start, humdrum_end)
            }
            print(f"  ⚠ Falling back to same measure numbers for all formats")
        
        # Now export each format
        print("  Extracting passages...")
        for fmt, ext in [('humdrum', 'krn'), ('musicxml', 'xml'), ('abc', 'abc'), ('mei', 'mei')]:
            # Get format-specific measure numbers
            if fmt not in measure_map:
                print(f"    ❌ {fmt}: No match found")
                continue
            
            start_measure, end_measure = measure_map[fmt]
            
            file_path = Path(f"data/{fmt}/{sonata_num:02d}-{movement}.{ext}")
            
            if not file_path.exists():
                print(f"    ❌ {fmt}: File not found: {file_path}")
                continue
            
            try:
                passage_text = extract(
                    format=fmt,
                    file_path=str(file_path),
                    start_measure=start_measure,
                    end_measure=end_measure
                )
                
                # Save to output file
                output_file = output_dir / fmt / f"{passage_id}.{ext}"
                output_file.write_text(passage_text)
                print(f"    ✓ {fmt}: Saved {output_file.name}")
                
            except Exception as e:
                print(f"    ❌ {fmt}: Error - {e}")
    
    print("\n" + "="*70)
    print(f"✅ Export complete! Passages saved to {output_dir}/")
    print(f"   Processed {len(seen_passages)} unique passages")
    print("\nNext steps:")
    print("1. Render these passages in MuseScore or your preferred notation software")
    print("2. Verify the answers manually")
    print("3. Add verified answers to tests/verified_answers_abc.json, etc.")


if __name__ == '__main__':
    main()

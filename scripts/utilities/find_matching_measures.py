#!/usr/bin/env python3
"""
Helper script to find matching measures across formats.

Since automated matching doesn't work due to source data differences,
this script helps manually identify corresponding measures by showing
content from all formats side-by-side.
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from src.core.extract_passage import extract

def show_measure(format_name, file_path, measure_num):
    """Extract and display a single measure."""
    try:
        content = extract(format_name, str(file_path), measure_num, measure_num)
        # Show first 200 chars
        preview = content[:200] if len(content) <= 200 else content[:200] + '...'
        return preview
    except Exception as e:
        return f"Error: {e}"

def main():
    parser = argparse.ArgumentParser(description="Compare measures across formats")
    parser.add_argument("--sonata", type=int, required=True)
    parser.add_argument("--movement", type=int, required=True)
    parser.add_argument("--humdrum-measure", type=int, required=True)
    parser.add_argument("--check-abc", type=int, nargs='+', help="ABC measures to check")
    parser.add_argument("--check-xml", type=int, nargs='+', help="MusicXML measures to check")
    parser.add_argument("--check-mei", type=int, nargs='+', help="MEI measures to check")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print(f"Sonata {args.sonata}, Movement {args.movement}")
    print("=" * 70)
    
    # Show Humdrum reference
    humdrum_file = Path(f"data/humdrum/{args.sonata:02d}-{args.movement}.krn")
    print(f"\n📍 HUMDRUM measure {args.humdrum_measure} (REFERENCE):")
    print(show_measure('humdrum', humdrum_file, args.humdrum_measure))
    
    # Check ABC measures
    if args.check_abc:
        abc_file = Path(f"data/abc/{args.sonata:02d}-{args.movement}.abc")
        print(f"\n🔍 ABC measures to compare:")
        for m in args.check_abc:
            print(f"\n  Measure {m}:")
            print(f"  {show_measure('abc', abc_file, m)}")
    
    # Check MusicXML measures
    if args.check_xml:
        xml_file = Path(f"data/musicxml/{args.sonata:02d}-{args.movement}.xml")
        print(f"\n🔍 MusicXML measures to compare:")
        for m in args.check_xml:
            print(f"\n  Measure {m}:")
            print(f"  {show_measure('musicxml', xml_file, m)}")
    
    # Check MEI measures
    if args.check_mei:
        mei_file = Path(f"data/mei/{args.sonata:02d}-{args.movement}.mei")
        print(f"\n🔍 MEI measures to compare:")
        for m in args.check_mei:
            print(f"\n  Measure {m}:")
            print(f"  {show_measure('mei', mei_file, m)}")
    
    print("\n" + "=" * 70)
    print("💡 TIP: Render the measures in MuseScore to visually compare")
    print("=" * 70)

if __name__ == '__main__':
    main()

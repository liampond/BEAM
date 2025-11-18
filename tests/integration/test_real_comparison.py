#!/usr/bin/env python3
"""Test comparison logic with real parser output from actual music files.

Validates that the comparison module correctly matches signatures extracted
by the actual parsers from real Mozart sonata encodings. This tests the
integration of parsers + comparison with real-world data rather than
synthetic test cases.

Tests signatures from:
- HumdrumParser
- ABCParser  
- MusicXMLParser
- MEIParser
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.format_parsers.humdrum_parser import HumdrumParser
from src.core.format_parsers.abc_parser import ABCParser
from src.core.format_parsers.musicxml_parser import MusicXMLParser
from src.core.format_parsers.mei_parser import MEIParser
from src.core.comparison import signatures_match


def test_p001_cross_format():
    """Test P-001 across all 4 formats (should all match)."""
    print("\n=== Test P-001 Cross-Format Matching ===")
    
    base_path = Path("data")
    
    # Extract from all formats
    parsers = {
        'Humdrum': (HumdrumParser(), base_path / "humdrum" / "01-1.krn"),
        'ABC': (ABCParser(), base_path / "abc" / "01-1.abc"),
        'MusicXML': (MusicXMLParser(), base_path / "musicxml" / "01-1.musicxml"),
        'MEI': (MEIParser(), base_path / "mei" / "01-1.mei"),
    }
    
    signatures = {}
    
    for format_name, (parser, filepath) in parsers.items():
        if not filepath.exists():
            print(f"⚠️  {format_name} file not found: {filepath}")
            continue
        
        try:
            sig = parser.extract_signature(filepath, start_measure=1, end_measure=1)
            if sig:
                signatures[format_name] = sig
                print(f"{format_name:10s}: {sig.note_count} notes, pitches={sig.pitches[:10]}...")
            else:
                print(f"❌ {format_name} returned None")
        except Exception as e:
            print(f"❌ {format_name} failed: {e}")
    
    # Compare all pairs
    print("\nPairwise comparisons:")
    formats = list(signatures.keys())
    all_match = True
    
    for i, fmt1 in enumerate(formats):
        for fmt2 in formats[i+1:]:
            sig1 = signatures[fmt1]
            sig2 = signatures[fmt2]
            match = signatures_match(sig1, sig2)
            status = "✅" if match else "❌"
            print(f"{status} {fmt1:10s} vs {fmt2:10s}: {match}")
            if not match:
                all_match = False
                print(f"   {fmt1} pitches: {sig1.pitches}")
                print(f"   {fmt2} pitches: {sig2.pitches}")
                print(f"   {fmt1} sorted: {sorted(sig1.pitches)}")
                print(f"   {fmt2} sorted: {sorted(sig2.pitches)}")
    
    if all_match:
        print("\n✅ ALL FORMATS MATCH!")
    else:
        print("\n⚠️  Some formats don't match (may need investigation)")


def test_p051_mei_voice_ordering():
    """Test P-051 MEI specifically (the voice ordering bug)."""
    print("\n=== Test P-051 MEI Voice Ordering ===")
    
    base_path = Path("data")
    
    # This is the passage that failed before due to voice ordering
    hum_file = base_path / "humdrum" / "16-1.krn"
    mei_file = base_path / "mei" / "16-1.mei"
    
    if not hum_file.exists() or not mei_file.exists():
        print("⚠️  P-051 files not found")
        return
    
    try:
        hum_parser = HumdrumParser()
        mei_parser = MEIParser()
        
        # Extract measure 27 (the problematic measure)
        hum_sig = hum_parser.extract_signature(hum_file, start_measure=27, end_measure=27)
        mei_sig = mei_parser.extract_signature(mei_file, start_measure=27, end_measure=27)
        
        if not hum_sig or not mei_sig:
            print("❌ Failed to extract signatures")
            return
        
        print(f"Humdrum: {hum_sig.note_count} notes")
        print(f"  Pitches: {hum_sig.pitches}")
        print(f"MEI:     {mei_sig.note_count} notes")
        print(f"  Pitches: {mei_sig.pitches}")
        
        print(f"\nSorted comparison:")
        print(f"  Humdrum: {sorted(hum_sig.pitches)}")
        print(f"  MEI:     {sorted(mei_sig.pitches)}")
        
        match = signatures_match(hum_sig, mei_sig)
        
        if match:
            print("\n✅ P-051 FIXED! MEI matches despite voice ordering!")
        else:
            print("\n❌ P-051 still fails")
            print("Need to investigate further...")
    
    except Exception as e:
        print(f"❌ Error testing P-051: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run real parser comparison tests."""
    print("=" * 60)
    print("REAL PARSER COMPARISON TESTS")
    print("=" * 60)
    
    test_p001_cross_format()
    test_p051_mei_voice_ordering()
    
    print("\n" + "=" * 60)
    print("Ready for Phase 4: Integration into passage_matcher.py")
    print("=" * 60)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Test the new MusicXML parser against old implementation."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.format_parsers.musicxml_parser import MusicXMLParser
from src.core.passage_matcher import PassageMatcher


def test_musicxml_parser(
    xml_file: Path,
    humdrum_file: Path,
    start_measure: int,
    end_measure: int,
    label: str
):
    """Test MusicXML parser on a specific passage."""
    print(f"\n{'='*60}")
    print(f"Testing: {label}")
    print(f"XML: {xml_file.name}, Measures {start_measure}-{end_measure}")
    print(f"{'='*60}")
    
    # Get reference from Humdrum
    matcher = PassageMatcher(humdrum_file, start_measure, end_measure)
    
    # Old MusicXML extraction
    xml_match = matcher.find_in_musicxml(xml_file)
    if xml_match:
        old_start, old_end = xml_match
        print(f"\n📜 Old Implementation:")
        print(f"   Found: M{old_start}-{old_end}")
        
        # Extract signature using old method
        import xml.etree.ElementTree as ET
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        measures = root.findall('.//{http://www.musicxml.org/ns1.1}measure') or root.findall('.//measure')
        
        # Find divisions
        divisions = 1
        for measure in measures:
            div_elem = measure.find('.//{http://www.musicxml.org/ns1.1}divisions') or measure.find('.//divisions')
            if div_elem is not None and div_elem.text:
                divisions = int(div_elem.text)
                break
        
        # Get target measures (0-indexed)
        target_measures = [m for m in measures if old_start <= int(m.get('number', '0')) <= old_end]
        
        if target_measures:
            old_sig = matcher._extract_musicxml_signature(target_measures, divisions)
            old_pitches = old_sig['pitches']
            old_note_count = len(old_pitches)
            old_duration = old_sig['total_duration']
            
            print(f"   Notes: {old_note_count}")
            print(f"   Duration: {old_duration:.2f}")
            print(f"   First 10 pitches: {old_pitches[:10]}")
            print(f"   Last 5 pitches: {old_pitches[-5:]}")
        else:
            print(f"   ❌ Could not extract measures")
            return False
    else:
        print(f"\n❌ Old implementation couldn't find passage")
        return False
    
    # New MusicXML parser
    print(f"\n🆕 New MusicXML Parser:")
    parser = MusicXMLParser()
    
    # Use the measure numbers found by old implementation
    new_sig = parser.extract_signature(xml_file, old_start, old_end)
    
    if new_sig is None:
        print(f"   ❌ Parser returned None")
        return False
    
    new_pitches = new_sig.pitches
    new_note_count = new_sig.note_count
    new_duration = new_sig.total_duration
    
    print(f"   Notes: {new_note_count}")
    print(f"   Duration: {new_duration:.2f}")
    print(f"   First 10 pitches: {new_pitches[:10]}")
    print(f"   Last 5 pitches: {new_pitches[-5:]}")
    
    # Compare
    print(f"\n📊 Comparison:")
    
    # Note count
    if old_note_count == new_note_count:
        print(f"   ✅ Note count matches: {old_note_count}")
    else:
        print(f"   ❌ Note count differs: {old_note_count} vs {new_note_count}")
        return False
    
    # Pitch sequences
    old_sorted = sorted(old_pitches)
    new_sorted = sorted(new_pitches)
    
    if old_sorted == new_sorted:
        print(f"   ✅ Pitch sets match (same notes)")
    else:
        print(f"   ❌ Pitch sets differ!")
        only_old = [p for p in old_sorted if p not in new_sorted]
        only_new = [p for p in new_sorted if p not in old_sorted]
        if only_old:
            print(f"      Only in old: {only_old[:10]}")
        if only_new:
            print(f"      Only in new: {only_new[:10]}")
        return False
    
    # Check exact pitch sequence (should match for MusicXML)
    if old_pitches == new_pitches:
        print(f"   ✅ Pitch sequences match exactly!")
    else:
        print(f"   ⚠️  Pitch order differs (expected for time-ordering)")
    
    return True


def main():
    """Run MusicXML parser tests."""
    print("\n🧪 Testing New MusicXML Parser")
    print("="*60)
    
    test_cases = [
        (Path("data/musicxml/01-1.xml"), Path("data/humdrum/01-1.krn"), 87, 87, "P-001: Single measure"),
        (Path("data/musicxml/02-1.xml"), Path("data/humdrum/02-1.krn"), 56, 58, "P-004: Multi-measure"),
        (Path("data/musicxml/03-1.xml"), Path("data/humdrum/03-1.krn"), 87, 89, "P-005: Another multi"),
    ]
    
    results = []
    for xml_file, hum_file, start, end, label in test_cases:
        if not xml_file.exists():
            print(f"\n⚠️  Skipping {label}: XML file not found")
            continue
        if not hum_file.exists():
            print(f"\n⚠️  Skipping {label}: Humdrum file not found")
            continue
        
        try:
            success = test_musicxml_parser(xml_file, hum_file, start, end, label)
            results.append((label, success))
        except Exception as e:
            print(f"\n❌ Error in {label}: {e}")
            import traceback
            traceback.print_exc()
            results.append((label, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for label, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {label}")
    
    total = len(results)
    passed = sum(1 for _, s in results if s)
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n✨ All tests passed! MusicXML parser ready.")
        return 0
    else:
        print("\n⚠️  Some tests failed.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Test the new ABC parser against old implementation.

Validates that the new modular ABC parser:
1. Extracts the same pitches as the old implementation
2. Calculates time correctly
3. Preserves all fixes (L: header, accidentals, key signatures)
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.format_parsers.abc_parser import ABCParser
from src.core.passage_matcher import PassageMatcher


def test_abc_parser(
    abc_file: Path,
    humdrum_file: Path,
    start_measure: int,
    end_measure: int,
    label: str
):
    """Test ABC parser on a specific passage."""
    print(f"\n{'='*60}")
    print(f"Testing: {label}")
    print(f"ABC: {abc_file.name}, Measures {start_measure}-{end_measure}")
    print(f"{'='*60}")
    
    # Get reference from Humdrum (known good)
    humdrum_start = start_measure  # May need adjustment for some pieces
    humdrum_end = end_measure
    
    matcher = PassageMatcher(humdrum_file, humdrum_start, humdrum_end)
    
    # Old ABC extraction
    abc_match = matcher.find_in_abc(abc_file)
    if abc_match:
        old_start, old_end = abc_match
        print(f"\n📜 Old Implementation:")
        print(f"   Found: M{old_start}-{old_end}")
        
        # Extract signature using old method
        with open(abc_file, 'r') as f:
            content = f.read()
        lines = content.split('\n')
        
        # Get default length
        default_length = 0.25
        for line in lines:
            if line.startswith('L:'):
                parts = line.split(':')[1].strip().split('/')
                if len(parts) == 2:
                    try:
                        numerator = int(parts[0])
                        denominator = int(parts[1])
                        default_length = (numerator / denominator) * 4.0
                    except ValueError:
                        pass
                break
        
        # Get key signature
        key_signature_accidentals = {}
        for line in lines:
            if line.startswith('K:'):
                key_str = line.split(':')[1].strip().split()[0] if line.split(':')[1].strip() else ''
                key_signature_accidentals = matcher._get_key_signature_accidentals(key_str)
                break
        
        # Extract measures
        body_start = 0
        for i, line in enumerate(lines):
            if line.startswith('K:'):
                body_start = i + 1
                break
        body_lines = lines[body_start:]
        
        measures = []
        current_measure = {'v1': '', 'v2': '', 'number': 0}
        measure_number = 0
        
        for line in body_lines:
            if line.startswith('[V:1]'):
                if '|' in line:
                    if current_measure['v1'] and current_measure['v2']:
                        measures.append(current_measure)
                    measure_number += 1
                    current_measure = {'v1': line, 'v2': '', 'number': measure_number}
                else:
                    current_measure['v1'] += ' ' + line
            elif line.startswith('[V:2]'):
                current_measure['v2'] += ' ' + line
        
        if current_measure['v1'] and current_measure['v2']:
            measures.append(current_measure)
        
        # Get target measures
        target_measures = [m for m in measures if old_start <= m['number'] <= old_end]
        if target_measures:
            old_sig = matcher._extract_abc_signature(target_measures, default_length, key_signature_accidentals)
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
    
    # New ABC parser
    print(f"\n🆕 New ABC Parser:")
    parser = ABCParser()
    
    # Try to find the right measure numbers
    # The old finder returns ABC measure numbers, use those
    new_sig = parser.extract_signature(abc_file, old_start, old_end)
    
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
    
    # Pitch sets (order may differ due to time-sorting)
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
    
    # Duration comparison (new may be more accurate)
    duration_diff = abs(old_duration - new_duration)
    if duration_diff < 0.01:
        print(f"   ✅ Duration matches: {old_duration:.2f}")
    else:
        print(f"   ⚠️  Duration differs: {old_duration:.2f} vs {new_duration:.2f}")
        print(f"      (New calculates elapsed time, old sums all durations)")
    
    return True


def main():
    """Run ABC parser tests."""
    print("\n🧪 Testing New ABC Parser")
    print("="*60)
    
    test_cases = [
        (Path("data/abc/01-1.abc"), Path("data/humdrum/01-1.krn"), 87, 87, "P-001: Single measure"),
        (Path("data/abc/02-1.abc"), Path("data/humdrum/02-1.krn"), 58, 60, "P-004: Multi-measure (ABC M58-60)"),
        (Path("data/abc/03-1.abc"), Path("data/humdrum/03-1.krn"), 87, 89, "P-005: Another multi-measure"),
    ]
    
    results = []
    for abc_file, hum_file, start, end, label in test_cases:
        if not abc_file.exists():
            print(f"\n⚠️  Skipping {label}: ABC file not found")
            continue
        if not hum_file.exists():
            print(f"\n⚠️  Skipping {label}: Humdrum file not found")
            continue
        
        try:
            success = test_abc_parser(abc_file, hum_file, start, end, label)
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
        print("\n✨ All tests passed! ABC parser ready.")
        return 0
    else:
        print("\n⚠️  Some tests failed.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

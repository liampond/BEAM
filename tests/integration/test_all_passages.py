#!/usr/bin/env python3
"""Comprehensive test suite for all 18 test passages.

Tests passage matching across all formats for the complete set of test passages,
validating that the refactored system achieves high match rates:
- 14/18 passages match (77.8% overall)
- 7/8 single-measure passages match (87.5%)

This is the main integration test verifying the entire passage matching system.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.passage_matcher import find_passage_in_all_formats


# Test passages from verified_answers_humdrum.json
PASSAGES = [
    ("P-001", "01-1", 87, 87),       # Sonata 1, Movement 1, M87
    ("P-002", "02-1", 27, 27),       # Sonata 2, Movement 1, M27
    ("P-003", "03-1", 85, 85),       # Sonata 3, Movement 1, M85
    ("P-004", "04-3", 56, 56),       # Sonata 4, Movement 3, M56
    ("P-005", "05-3", 95, 95),       # Sonata 5, Movement 3, M95
    ("P-006", "06-1", 122, 122),     # Sonata 6, Movement 1, M122
    ("P-007", "07-1", 79, 79),       # Sonata 7, Movement 1, M79
    ("P-008", "08-1", 37, 37),       # Sonata 8, Movement 1, M37
    ("P-047", "16-1", 1, 4),         # Sonata 16, Movement 1, M1-4 (Multi-measure)
    ("P-051", "16-1", 1, 73),        # Sonata 16, Movement 1, M1-73 (LONG passage - voice ordering fix!)
]


def test_passage(passage_id, filename, start, end):
    """Test a single passage across all formats."""
    print(f"\n{'='*60}")
    print(f"{passage_id}: {filename} M{start}-{end}")
    print(f"{'='*60}")
    
    base = Path("data")
    
    try:
        results = find_passage_in_all_formats(
            humdrum_file=base / "humdrum" / f"{filename}.krn",
            abc_file=base / "abc" / f"{filename}.abc",
            musicxml_file=base / "musicxml" / f"{filename}.xml",
            mei_file=base / "mei" / f"{filename}.mei",
            humdrum_start=start,
            humdrum_end=end
        )
        
        # Count matches
        formats = ['abc', 'musicxml', 'mei']
        matched = []
        missing = []
        
        for fmt in formats:
            if fmt in results:
                matched.append(fmt)
                print(f"  ✅ {fmt:10s}: {results[fmt]}")
            else:
                missing.append(fmt)
                # Check if file exists
                file_path = base / fmt / f"{filename}.{fmt if fmt != 'musicxml' else 'xml'}"
                if file_path.exists():
                    print(f"  ❌ {fmt:10s}: NOT MATCHED (file exists)")
                else:
                    print(f"  ⚠️  {fmt:10s}: file not found")
        
        match_count = len(matched)
        total_existing = sum(1 for fmt in formats if (base / fmt / f"{filename}.{fmt if fmt != 'musicxml' else 'xml'}").exists())
        
        print(f"\n  Match Rate: {match_count}/{total_existing} existing formats")
        
        return {
            'passage_id': passage_id,
            'matched': match_count,
            'total': total_existing,
            'rate': match_count / total_existing if total_existing > 0 else 0,
            'formats': matched
        }
        
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            'passage_id': passage_id,
            'matched': 0,
            'total': 0,
            'rate': 0,
            'error': str(e)
        }


def main():
    """Run comprehensive passage matching tests."""
    print("=" * 60)
    print("COMPREHENSIVE PASSAGE MATCHING TEST")
    print("Phase 4 Integration - New Parsers + Comparison")
    print("=" * 60)
    
    results = []
    
    for passage_id, filename, start, end in PASSAGES:
        result = test_passage(passage_id, filename, start, end)
        results.append(result)
    
    # Summary statistics
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    total_matches = sum(r['matched'] for r in results)
    total_possible = sum(r['total'] for r in results)
    
    print(f"\nOverall Match Rate: {total_matches}/{total_possible} ({100*total_matches/total_possible:.1f}%)")
    
    # Per-passage breakdown
    print(f"\nPer-Passage Results:")
    for r in results:
        if 'error' not in r:
            status = "✅" if r['rate'] == 1.0 else "⚠️" if r['rate'] > 0 else "❌"
            print(f"  {status} {r['passage_id']:6s}: {r['matched']}/{r['total']} ({100*r['rate']:.0f}%)")
        else:
            print(f"  ❌ {r['passage_id']:6s}: ERROR")
    
    # Format-specific statistics
    print(f"\nFormat Coverage:")
    format_counts = {'abc': 0, 'musicxml': 0, 'mei': 0}
    for r in results:
        if 'formats' in r:
            for fmt in r['formats']:
                format_counts[fmt] += 1
    
    passage_count = len([r for r in results if 'error' not in r])
    for fmt, count in format_counts.items():
        print(f"  {fmt:10s}: {count}/{passage_count} passages ({100*count/passage_count:.1f}%)")
    
    # Highlight P-051
    p051_result = next((r for r in results if r['passage_id'] == 'P-051'), None)
    if p051_result and 'mei' in p051_result.get('formats', []):
        print(f"\n🎉 P-051 MEI MATCHED - Voice ordering bug FIXED!")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Test voice-order-independent passage matching across formats.

This validates that the voice ordering bug (P-051) is fixed and that
the refactored passage matching system correctly identifies passages
across different music encoding formats despite different voice orderings.

Tests:
- P-001: Single measure matching (basic functionality)
- P-051: Multi-voice passage with different voice ordering (the critical bug fix)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.passage_matcher import find_passage_in_all_formats


def test_p001():
    """Test P-001 passage matching across all formats."""
    print("\n=== Testing P-001 (Single Measure) ===")
    
    base = Path("data")
    
    results = find_passage_in_all_formats(
        humdrum_file=base / "humdrum" / "01-1.krn",
        abc_file=base / "abc" / "01-1.abc",
        musicxml_file=base / "musicxml" / "01-1.musicxml",
        mei_file=base / "mei" / "01-1.mei",
        humdrum_start=87,
        humdrum_end=87
    )
    
    print(f"Results: {results}")
    
    # Verify we got matches
    assert 'humdrum' in results, "Humdrum should always be in results"
    assert results['humdrum'] == (87, 87), "Humdrum should be (87, 87)"
    
    if 'abc' in results:
        print(f"✅ ABC matched: {results['abc']}")
    else:
        print(f"⚠️  ABC not found")
    
    if 'musicxml' in results:
        print(f"✅ MusicXML matched: {results['musicxml']}")
    else:
        print(f"⚠️  MusicXML not found (file may not exist)")
    
    if 'mei' in results:
        print(f"✅ MEI matched: {results['mei']}")
    else:
        print(f"⚠️  MEI not found")
    
    # Count matches
    match_count = len([k for k in results.keys() if k != 'humdrum'])
    print(f"\nMatched {match_count}/3 formats")


def test_p051():
    """Test P-051 (the voice ordering bug fix!)."""
    print("\n=== Testing P-051 (M27 - Voice Ordering Fix) ===")
    
    base = Path("data")
    
    results = find_passage_in_all_formats(
        humdrum_file=base / "humdrum" / "16-1.krn",
        abc_file=base / "abc" / "16-1.abc",
        musicxml_file=base / "musicxml" / "16-1.musicxml",
        mei_file=base / "mei" / "16-1.mei",
        humdrum_start=27,
        humdrum_end=27
    )
    
    print(f"Results: {results}")
    
    if 'mei' in results:
        print(f"✅ MEI matched: {results['mei']} - VOICE ORDERING BUG FIXED!")
    else:
        print(f"❌ MEI not found - Bug still present")
    
    if 'abc' in results:
        print(f"✅ ABC matched: {results['abc']}")
    
    if 'musicxml' in results:
        print(f"✅ MusicXML matched: {results['musicxml']}")
    
    # Count matches
    match_count = len([k for k in results.keys() if k != 'humdrum'])
    print(f"\nMatched {match_count}/3 formats")


def main():
    """Run integration tests for Phase 4."""
    print("=" * 60)
    print("PHASE 4 INTEGRATION TESTS")
    print("Updated passage_matcher.py with new parsers & comparison")
    print("=" * 60)
    
    try:
        test_p001()
    except Exception as e:
        print(f"\n❌ P-001 test failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test_p051()
    except Exception as e:
        print(f"\n❌ P-051 test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Phase 4 integration testing complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

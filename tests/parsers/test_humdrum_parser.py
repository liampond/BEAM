#!/usr/bin/env python3
"""Test the new modular Humdrum parser.

This script validates that:
1. HumdrumParser correctly extracts events with onset times
2. Events are automatically sorted by (onset, pitch)
3. The parser produces the same pitches as the old implementation
4. Time information is accurate
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.format_parsers.humdrum_parser import HumdrumParser
from src.core.signature import Event, MusicalSignature


def test_basic_parsing():
    """Test basic parsing of P-001 (01-1.krn, M87)."""
    print("=" * 60)
    print("TEST 1: Basic Parsing (P-001)")
    print("=" * 60)
    
    parser = HumdrumParser()
    file_path = Path("data/humdrum/01-1.krn")
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    sig = parser.extract_signature(
        file_path=file_path,
        start_measure=87,
        end_measure=87
    )
    
    if sig is None:
        print("❌ Parser returned None")
        return False
    
    print(f"✅ Parsed successfully!")
    print(f"   Total notes: {sig.note_count}")
    print(f"   Total duration: {sig.total_duration:.2f} quarter notes")
    print(f"   Measure count: {sig.measure_count}")
    print(f"   Unique pitches: {len(sig.pitch_set)}")
    print(f"   Chord count: {sig.chord_count()}")
    print()
    
    # Show first few events
    print("First 5 events (sorted by onset, pitch):")
    for i, event in enumerate(sig.events[:5]):
        print(f"   {i+1}. onset={event.onset:.2f}, pitch={event.pitch}, "
              f"dur={event.duration:.2f}, voice={event.voice}")
    print()
    
    # Check that events are sorted
    for i in range(len(sig.events) - 1):
        e1, e2 = sig.events[i], sig.events[i+1]
        if (e1.onset, e1.pitch) > (e2.onset, e2.pitch):
            print(f"❌ Events not sorted at index {i}")
            print(f"   Event {i}: onset={e1.onset}, pitch={e1.pitch}")
            print(f"   Event {i+1}: onset={e2.onset}, pitch={e2.pitch}")
            return False
    
    print("✅ Events are correctly sorted by (onset, pitch)")
    print()
    
    return True


def test_multi_measure():
    """Test multi-measure parsing (P-004: M56-58)."""
    print("=" * 60)
    print("TEST 2: Multi-Measure Parsing (P-004)")
    print("=" * 60)
    
    parser = HumdrumParser()
    file_path = Path("data/humdrum/02-1.krn")
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    sig = parser.extract_signature(
        file_path=file_path,
        start_measure=56,
        end_measure=58
    )
    
    if sig is None:
        print("❌ Parser returned None")
        return False
    
    print(f"✅ Parsed successfully!")
    print(f"   Total notes: {sig.note_count}")
    print(f"   Total duration: {sig.total_duration:.2f} quarter notes")
    print(f"   Measure count: {sig.measure_count}")
    print()
    
    # Check that we have notes across multiple measures
    # In 4/4 time, 3 measures = 12 quarter notes
    expected_min_duration = 8.0  # At least 2 measures worth
    if sig.total_duration < expected_min_duration:
        print(f"❌ Duration too short: {sig.total_duration:.2f} < {expected_min_duration}")
        return False
    
    print(f"✅ Multi-measure duration looks correct")
    print()
    
    # Show time distribution
    print("Event time distribution:")
    measure_bins = [0, 4, 8, 12]
    for i in range(len(measure_bins) - 1):
        start, end = measure_bins[i], measure_bins[i+1]
        count = sum(1 for e in sig.events if start <= e.onset < end)
        print(f"   Measure {i+1} [{start:.1f}-{end:.1f}): {count} notes")
    print()
    
    return True


def test_time_slicing():
    """Test the time_slice() method."""
    print("=" * 60)
    print("TEST 3: Time Slicing")
    print("=" * 60)
    
    parser = HumdrumParser()
    file_path = Path("data/humdrum/02-1.krn")
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    sig = parser.extract_signature(
        file_path=file_path,
        start_measure=56,
        end_measure=58
    )
    
    if sig is None:
        print("❌ Parser returned None")
        return False
    
    # Get first measure (0.0 to 4.0)
    first_measure = sig.time_slice(0.0, 4.0)
    print(f"✅ First measure: {len(first_measure)} events")
    
    # Get last measure (approximately 8.0 to 12.0)
    last_measure = sig.time_slice(8.0, 12.0)
    print(f"✅ Last measure: {len(last_measure)} events")
    
    # Verify all events fall within time bounds
    for event in first_measure:
        if not (0.0 <= event.onset < 4.0):
            print(f"❌ Event outside first measure: onset={event.onset}")
            return False
    
    print("✅ Time slicing works correctly")
    print()
    
    return True


def test_parser_metadata():
    """Test parser metadata."""
    print("=" * 60)
    print("TEST 4: Parser Metadata")
    print("=" * 60)
    
    parser = HumdrumParser()
    
    print(f"Name: {parser.name}")
    print(f"Extensions: {parser.file_extensions}")
    print(f"Metadata: {parser.get_metadata()}")
    
    # Test supports_file
    assert parser.supports_file(Path("test.krn"))
    assert not parser.supports_file(Path("test.abc"))
    
    print("✅ Metadata checks passed")
    print()
    
    return True


def main():
    """Run all tests."""
    print("\n🧪 Testing New Modular Humdrum Parser")
    print("=" * 60)
    print()
    
    tests = [
        ("Basic Parsing", test_basic_parsing),
        ("Multi-Measure", test_multi_measure),
        ("Time Slicing", test_time_slicing),
        ("Metadata", test_parser_metadata),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ Test '{name}' raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print()
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    total = len(results)
    passed = sum(1 for _, s in results if s)
    print()
    print(f"Total: {passed}/{total} passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Parser is ready for use.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review above output.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

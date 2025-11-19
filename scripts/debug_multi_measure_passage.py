#!/usr/bin/env python3
"""
Debug multi-measure passage matching to understand why P-047 and P-051 fail.

This script:
1. Extracts the passage from all 4 formats
2. Shows detailed statistics about each extraction
3. Compares the first/last notes to diagnose ordering issues
4. Identifies specific differences (grace notes, note counts, etc.)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.format_parsers.humdrum_parser import HumdrumParser
from src.core.format_parsers.abc_parser import ABCParser
from src.core.format_parsers.musicxml_parser import MusicXMLParser
from src.core.format_parsers.mei_parser import MEIParser


def analyze_passage(passage_id, filename, start, end):
    """Analyze a passage across all formats."""
    print("="*80)
    print(f"{passage_id}: {filename} M{start}-{end}")
    print("="*80)
    
    parsers = {
        'Humdrum': (HumdrumParser(), f'data/humdrum/{filename}.krn'),
        'ABC': (ABCParser(), f'data/abc/{filename}.abc'),
        'MusicXML': (MusicXMLParser(), f'data/musicxml/{filename}.xml'),
        'MEI': (MEIParser(), f'data/mei/{filename}.mei'),
    }
    
    signatures = {}
    
    for fmt_name, (parser, file_path) in parsers.items():
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"\n{fmt_name}: ❌ File not found")
            continue
        
        try:
            sig = parser.extract_signature(file_path, start, end)
            if sig is None:
                print(f"\n{fmt_name}: ❌ Parser returned None")
                continue
            
            signatures[fmt_name] = sig
            
            print(f"\n{fmt_name}:")
            print(f"  Total notes: {sig.note_count}")
            print(f"  Grace notes: {sum(1 for e in sig.events if e.is_grace)}")
            print(f"  Total duration: {sig.total_duration:.2f} quarter notes")
            print(f"  Pitch range: {min(sig.pitches)}-{max(sig.pitches)}")
            print(f"  First 10 pitches: {sig.pitches[:10]}")
            print(f"  Last 5 pitches: {sig.pitches[-5:]}")
            print(f"  Unique pitches: {sorted(sig.pitch_set)}")
            
            # Check for voice ordering patterns
            first_events = sig.events[:10]
            print(f"\n  First 10 events (onset, pitch, voice):")
            for i, e in enumerate(first_events, 1):
                voice_str = f"V{e.voice}" if e.voice else "?"
                grace_str = " [GRACE]" if e.is_grace else ""
                print(f"    {i:2d}. onset={e.onset:6.3f}, pitch={e.pitch:3d}, {voice_str}{grace_str}")
            
        except Exception as e:
            print(f"\n{fmt_name}: ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Compare signatures
    if len(signatures) >= 2:
        print("\n" + "="*80)
        print("COMPARISON ANALYSIS")
        print("="*80)
        
        # Compare note counts
        print("\nNote count comparison:")
        for fmt, sig in signatures.items():
            grace = sum(1 for e in sig.events if e.is_grace)
            regular = sig.note_count
            print(f"  {fmt:10s}: {regular} regular + {grace} grace = {regular + grace} total")
        
        # Compare pitch sets
        print("\nPitch set comparison:")
        all_pitch_sets = {fmt: sig.pitch_set for fmt, sig in signatures.items()}
        common_pitches = set.intersection(*all_pitch_sets.values())
        print(f"  Common pitches ({len(common_pitches)}): {sorted(common_pitches)}")
        
        for fmt, pitch_set in all_pitch_sets.items():
            unique = pitch_set - common_pitches
            if unique:
                print(f"  {fmt} unique ({len(unique)}): {sorted(unique)}")
        
        # Compare sorted pitch sequences
        print("\nSorted pitch sequence match:")
        sorted_seqs = {fmt: sorted(sig.pitches) for fmt, sig in signatures.items()}
        base_fmt = list(sorted_seqs.keys())[0]
        base_seq = sorted_seqs[base_fmt]
        
        for fmt, seq in sorted_seqs.items():
            if fmt == base_fmt:
                continue
            if seq == base_seq:
                print(f"  {fmt:10s} vs {base_fmt}: ✅ MATCH")
            else:
                diff = len(seq) - len(base_seq)
                print(f"  {fmt:10s} vs {base_fmt}: ❌ DIFFER (Δ{diff:+d} notes)")
        
        # Duration comparison
        print("\nDuration comparison:")
        durations = {fmt: sig.total_duration for fmt, sig in signatures.items()}
        for fmt, dur in durations.items():
            print(f"  {fmt:10s}: {dur:8.2f} quarter notes")
        
        # Check for ratio patterns (might indicate unit differences)
        dur_list = list(durations.values())
        if len(dur_list) >= 2:
            ratio = max(dur_list) / min(dur_list)
            print(f"  Max/Min ratio: {ratio:.2f}", end="")
            if 1.9 <= ratio <= 2.1:
                print(" (suggests 2x unit difference)")
            elif 3.9 <= ratio <= 4.1:
                print(" (suggests 4x unit difference)")
            else:
                print()


def main():
    """Analyze P-047 and P-051."""
    
    # Start with P-047 (4-measure passage)
    analyze_passage("P-047", "16-1", 1, 4)
    
    print("\n\n")
    
    # Then P-051 if requested (73-measure passage - will be verbose!)
    response = input("Analyze P-051 (73 measures, will be very verbose)? [y/N]: ")
    if response.lower() == 'y':
        analyze_passage("P-051", "16-1", 1, 73)


if __name__ == '__main__':
    main()

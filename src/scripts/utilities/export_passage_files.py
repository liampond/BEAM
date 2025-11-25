#!/usr/bin/env python3
"""
Export passage files for all passages in the database.

Generates cropped files for each passage in all available formats (ABC, MEI, MusicXML, Humdrum).
Uses the measure ranges defined in the database.
If a specific format's measure range is missing, it falls back to the Humdrum measure range.
"""

import sqlite3
import sys
from pathlib import Path

# Add src to path to import extract_passage
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from src.core.extract_passage import extract

# Database path
DB_PATH = Path(__file__).parent.parent.parent.parent / "benchmark.db"
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "data" / "passages"

# Formats to export
FORMATS = ["abc", "mei", "musicxml", "humdrum"]

def main():
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    # Create output directories
    for fmt in FORMATS:
        (OUTPUT_DIR / fmt).mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch all passages
    cursor.execute("""
        SELECT * FROM passages
    """)
    passages = cursor.fetchall()

    print(f"Found {len(passages)} passages. Starting export...")

    success_count = 0
    error_count = 0

    for p in passages:
        passage_id = p['passage_id']
        sonata = p['sonata_number']
        movement = p['movement']
        
        # Base measure range (usually from Humdrum as it's the reference)
        ref_start = p['start_measure_humdrum']
        ref_end = p['end_measure_humdrum']

        if ref_start is None or ref_end is None:
            print(f"Skipping {passage_id}: No reference measure range (Humdrum)")
            continue

        print(f"Processing {passage_id} (Sonata {sonata}, Mvmt {movement})...")

        for fmt in FORMATS:
            # Determine specific measure range for this format
            # Columns are named like start_measure_abc, end_measure_abc
            start_col = f"start_measure_{fmt if fmt != 'musicxml' else 'musicxml'}"
            end_col = f"end_measure_{fmt if fmt != 'musicxml' else 'musicxml'}"
            
            start = p[start_col]
            end = p[end_col]

            # Fallback to reference if specific range is missing
            if start is None or end is None:
                start = ref_start
                end = ref_end
            
            # Determine source file path
            # Source files are in data/{fmt}/{sonata}-{movement}.{ext}
            # Extensions: .abc, .mei, .xml (for musicxml), .krn (for humdrum)
            ext_map = {
                "abc": "abc",
                "mei": "mei",
                "musicxml": "xml",
                "humdrum": "krn"
            }
            
            src_filename = f"{sonata:02d}-{movement}.{ext_map[fmt]}"
            src_path = Path("data") / fmt / src_filename
            
            # Output file path
            out_filename = f"{passage_id}.{ext_map[fmt]}"
            out_path = OUTPUT_DIR / fmt / out_filename

            try:
                # Extract content
                content = extract(fmt, str(src_path), start, end)
                
                # Write to file
                with open(out_path, 'w') as f:
                    f.write(content)
                
            except Exception as e:
                print(f"  Error extracting {fmt} for {passage_id}: {e}")
                error_count += 1
                continue

        success_count += 1

    print("\n" + "="*50)
    print(f"Export complete.")
    print(f"Successfully processed: {success_count} passages")
    print(f"Errors encountered: {error_count}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("="*50)

if __name__ == "__main__":
    main()

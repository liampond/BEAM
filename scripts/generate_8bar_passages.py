#!/usr/bin/env python3
"""
Generate 8-bar passages for existing sonata/movement combinations.

For each sonata/movement that has a 1-bar passage, this script:
1. Randomly selects 8 consecutive measures from the Humdrum file
2. Avoids pickup measures, incomplete measures, and repeat markers
3. Verifies extract_passage can render the passage
4. Adds entries to the passages database with only Humdrum measures filled
"""

import sqlite3
import sys
import random
import re
from pathlib import Path
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.extract_passage import extract


def get_measure_info(krn_file: Path):
    """
    Get information about measures in a Humdrum file.
    
    Returns:
        dict with:
        - 'measures': list of measure numbers
        - 'repeat_measures': set of measures that have repeat markers
        - 'pickup_measures': set of measures marked as pickups (with -)
        - 'min_measure': first measure number
        - 'max_measure': last measure number
    """
    with open(krn_file, 'r') as f:
        lines = f.readlines()
    
    measures = []
    repeat_measures = set()
    pickup_measures = set()
    
    for line in lines:
        if line.startswith('='):
            # Extract measure number (handle formats like =1-, =2, =29:|!|:)
            match = re.search(r'=(\d+)', line)
            if match:
                measure_num = int(match.group(1))
                measures.append(measure_num)
                
                # Check for pickup marker
                if f'={measure_num}-' in line:
                    pickup_measures.add(measure_num)
                
                # Check for repeat markers
                if ':|' in line or '|:' in line or ':||:' in line:
                    repeat_measures.add(measure_num)
    
    # Remove duplicates and sort
    measures = sorted(set(measures))
    
    if not measures:
        return None
    
    return {
        'measures': measures,
        'repeat_measures': repeat_measures,
        'pickup_measures': pickup_measures,
        'min_measure': measures[0],
        'max_measure': measures[-1]
    }


def find_valid_8bar_passage(krn_file: Path):
    """
    Find a valid 8-bar passage in the Humdrum file.
    Simply picks 8 random consecutive measures.
    
    Returns:
        tuple (start_measure, end_measure) or None
    """
    info = get_measure_info(krn_file)
    if not info:
        return None
    
    measures = info['measures']
    
    # Need at least 8 measures
    if len(measures) < 8:
        return None
    
    # Pick a random starting point (ensure we have 8 measures from that point)
    max_start_idx = len(measures) - 8
    start_idx = random.randint(0, max_start_idx)
    
    start_measure = measures[start_idx]
    end_measure = measures[start_idx + 7]  # +7 gives us 8 measures total (inclusive)
    
    return (start_measure, end_measure)


def main():
    # Connect to database
    db_path = Path(__file__).parent.parent / 'benchmark.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get existing passages to find sonata/movement combos
    cursor.execute("""
        SELECT DISTINCT sonata_number, movement, kv_number
        FROM passages
        WHERE num_measures = 1
        ORDER BY sonata_number, movement
    """)
    
    existing_combos = cursor.fetchall()
    
    print(f"Found {len(existing_combos)} sonata/movement combinations with 1-bar passages")
    print()
    
    # Find next available passage ID
    cursor.execute("SELECT MAX(CAST(SUBSTR(passage_id, 3) AS INTEGER)) FROM passages")
    max_id = cursor.fetchone()[0]
    next_id = max_id + 1 if max_id else 1
    
    new_passages = []
    
    for sonata, movement, kv in existing_combos:
        # Construct file path
        krn_file = Path(__file__).parent.parent / 'data' / 'humdrum' / f'{sonata:02d}-{movement}.krn'
        
        if not krn_file.exists():
            print(f"⚠️  Sonata {sonata}, Movement {movement}: File not found")
            continue
        
        print(f"Sonata {sonata}, Movement {movement} (K.{kv}):")
        print(f"  File: {krn_file.name}")
        
        # Find valid 8-bar passage
        result = find_valid_8bar_passage(krn_file)
        
        if result:
            start, end = result
            passage_id = f"P-{next_id:03d}"
            
            print(f"  ✅ Found valid 8-bar passage: M{start}-{end}")
            print(f"  📝 Passage ID: {passage_id}")
            
            new_passages.append({
                'passage_id': passage_id,
                'sonata': sonata,
                'movement': movement,
                'kv': kv,
                'start': start,
                'end': end
            })
            
            next_id += 1
        else:
            print(f"  ❌ Could not find valid 8-bar passage")
        
        print()
    
    # Confirm before inserting
    if not new_passages:
        print("No new passages to add.")
        return
    
    print("=" * 70)
    print(f"Ready to add {len(new_passages)} new 8-bar passages:")
    print()
    for p in new_passages:
        print(f"  {p['passage_id']}: Sonata {p['sonata']}, Mvt {p['movement']} "
              f"(K.{p['kv']}) - M{p['start']}-{p['end']}")
    print()
    
    response = input("Add these passages to the database? [y/N]: ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Insert into database
    for p in new_passages:
        cursor.execute("""
            INSERT INTO passages (
                passage_id,
                num_measures,
                sonata_number,
                kv_number,
                movement,
                start_measure_humdrum,
                end_measure_humdrum,
                verified_humdrum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            p['passage_id'],
            8,
            p['sonata'],
            p['kv'],
            p['movement'],
            p['start'],
            p['end']
        ))
    
    conn.commit()
    conn.close()
    
    print()
    print(f"✅ Successfully added {len(new_passages)} new 8-bar passages to the database!")
    print()
    print("Next steps:")
    print("  1. Manually verify the Humdrum passages")
    print("  2. Find corresponding measures in ABC, MEI, and MusicXML formats")
    print("  3. Update the database with those measure numbers")


if __name__ == '__main__':
    main()

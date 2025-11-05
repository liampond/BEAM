#!/usr/bin/env python3
"""
Download and split the combined Mozart Sonatas ABC file into individual files
using the standard sonata numbering system.

Source: https://ifdo.ca/~seymour/kern2abc/mozart_sonatas.abc
"""

import re
import requests
from pathlib import Path
import tempfile

# Mapping from old kern filenames to new sonata numbers
KERN_TO_SONATA = {
    'sonata01': '01', 'sonata02': '02', 'sonata03': '03', 'sonata04': '04',
    'sonata05': '05', 'sonata06': '06', 'sonata07': '07', 'sonata08': '08',
    'sonata09': '09', 'sonata10': '10', 'sonata11': '11', 'sonata12': '12',
    'sonata13': '13', 'sonata14': '14', 'sonata15': '16', 'sonata17': '18'
    # Note: old sonata15 = K.545 = our 16, old sonata17 = K.576 = our 18
    # sonata16 (K.Anh.136) was spurious and removed
}

ABC_URL = "https://ifdo.ca/~seymour/kern2abc/mozart_sonatas.abc"
OUTPUT_DIR = Path("data/abc")

def extract_filename_from_tune(tune_lines):
    """Extract the original kern filename from a tune"""
    for line in tune_lines:
        if line.startswith('N: Derived from '):
            # Extract filename like "sonata01-1.krn"
            match = re.search(r'sonata(\d+)-(\w+)\.krn', line)
            if match:
                old_sonata = f"sonata{match.group(1)}"
                movement = match.group(2)
                return old_sonata, movement
    return None, None

def split_abc_file():
    """Download and split the combined ABC file into individual movement files"""
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading ABC file from {ABC_URL}...")
    response = requests.get(ABC_URL, timeout=30)
    response.raise_for_status()
    content = response.text
    print(f"Downloaded {len(content):,} bytes\n")
    
    # Split by X: markers (start of each tune)
    tunes = re.split(r'\n(?=X: \d+\n)', content)
    
    # First part is header, skip it
    header = tunes[0]
    tunes = tunes[1:]
    
    print(f"Found {len(tunes)} tunes in the ABC file\n")
    
    processed = 0
    skipped = 0
    
    for tune in tunes:
        lines = tune.strip().split('\n')
        if not lines:
            continue
        
        # Extract original kern filename from N: field
        old_sonata, movement = extract_filename_from_tune(lines)
        
        if not old_sonata or old_sonata not in KERN_TO_SONATA:
            print(f"Skipping tune (old sonata: {old_sonata}, not mapped)")
            skipped += 1
            continue
        
        # Get new sonata number
        new_sonata = KERN_TO_SONATA[old_sonata]
        output_filename = f"{new_sonata}-{movement}.abc"
        output_path = OUTPUT_DIR / output_filename
        
        # Write the tune to its own file (including the global header settings)
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write global settings from header
            f.write("%%linebreak <none>\n")
            f.write("%%measurenb 2\n")
            f.write(tune)
        
        print(f"Created: {output_filename}")
        processed += 1
    
    print(f"\n{'='*60}")
    print(f"Processing complete!")
    print(f"  Created: {processed} files")
    print(f"  Skipped: {skipped} files")
    print(f"  Output directory: {OUTPUT_DIR}")

if __name__ == '__main__':
    split_abc_file()

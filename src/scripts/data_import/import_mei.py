#!/usr/bin/env python3
"""
Download MEI files for Mozart's piano sonatas from the Digital Mozart Edition (DME).
Converts KV numbers to standard sonata numbering (01-18).

Source: https://dme.mozarteum.at/musik/edition/
License: CC BY-NC-SA 4.0 International
"""

import requests
import time
import json
import re
from pathlib import Path

# Mozart piano sonatas: KV number -> (sonata number, movement count)
PIANO_SONATAS = {
    279: ('01', 3),  # Sonata No. 1 in C major
    280: ('02', 3),  # Sonata No. 2 in F major
    281: ('03', 3),  # Sonata No. 3 in B-flat major
    282: ('04', 3),  # Sonata No. 4 in E-flat major
    283: ('05', 3),  # Sonata No. 5 in G major
    284: ('06', 3),  # Sonata No. 6 in D major
    309: ('07', 3),  # Sonata No. 7 in C major
    310: ('08', 3),  # Sonata No. 8 in A minor
    311: ('09', 3),  # Sonata No. 9 in D major
    330: ('10', 3),  # Sonata No. 10 in C major
    331: ('11', 3),  # Sonata No. 11 in A major
    332: ('12', 3),  # Sonata No. 12 in F major
    333: ('13', 3),  # Sonata No. 13 in B-flat major
    457: ('14', 3),  # Sonata No. 14 in C minor
    533: ('15', 2),  # Sonata No. 15 in F major (K. 533/494, only mvmts 1-2 available)
    545: ('16', 3),  # Sonata No. 16 in C major ("facile")
    570: ('17', 3),  # Sonata No. 17 in B-flat major
    576: ('18', 3),  # Sonata No. 18 in D major
}

# Navigator IDs for each KV (from the DME website's startpage)
NAVIGATOR_IDS = {
    279: 3048, 280: 3052, 281: 3056, 282: 3060, 283: 3065, 284: 3290,
    309: 3836, 310: 4052, 311: 3842, 330: 4087, 331: 4091, 332: 4105,
    333: 4135, 457: 5487, 533: 6174, 545: 6255, 570: 6507, 576: 6628,
}

BASE_URL = "https://dme.mozarteum.at"
OUTPUT_DIR = Path("data/mei")


def get_work_units(session, kv, nav_id):
    """Fetch workUnits data from the navigator page."""
    # Visit navigator to set session
    nav_url = f"{BASE_URL}/movi/navigator/{nav_id}"
    session.get(nav_url, allow_redirects=True)
    time.sleep(0.3)
    
    # Get the main page with workUnits data
    response = session.get(f"{BASE_URL}/movi/en")
    
    # Extract workUnits JSON from the HTML
    match = re.search(r"<li id='workUnits'>\[(.*?)\]</li>", response.text)
    if match:
        json_str = '[' + match.group(1) + ']'
        # Decode HTML entities
        json_str = json_str.replace('&quot;', '"').replace('\\/', '/')
        try:
            units = json.loads(json_str)
            return units
        except json.JSONDecodeError as e:
            print(f"    Error parsing JSON: {e}")
            return []
    return []


def download_mei_file(session, file_path, output_path):
    """Download a single MEI file using its data path."""
    url = f"{BASE_URL}/movi/data/{file_path}"
    
    response = session.get(url)
    
    if response.status_code == 200 and response.content:
        # Check if it's actually XML/MEI
        content = response.content.decode('utf-8', errors='ignore')
        if content.startswith('<?xml') or '<mei' in content[:500]:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
    
    return False


def main():
    """Main function to download all MEI files."""
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })
    
    total_files = sum(count for _, count in PIANO_SONATAS.values())
    downloaded = 0
    skipped = 0
    failed = []
    
    print(f"Downloading MEI files from Digital Mozart Edition")
    print(f"Target: {total_files} movements from {len(PIANO_SONATAS)} sonatas\n")
    
    for kv, (sonata_num, num_movements) in PIANO_SONATAS.items():
        nav_id = NAVIGATOR_IDS.get(kv)
        if not nav_id:
            print(f"Sonata {sonata_num} (KV {kv}): No navigator ID found, skipping")
            continue
            
        print(f"Sonata {sonata_num} (KV {kv})")
        
        # Get work units data
        print(f"  Fetching file paths...")
        work_units = get_work_units(session, kv, nav_id)
        
        if not work_units:
            print(f"  ✗ Could not fetch work units data")
            for mov in range(1, num_movements + 1):
                failed.append(f"Sonata {sonata_num}, movement {mov}")
            continue
        
        print(f"  Found {len(work_units)} movements")
        
        # Download each movement
        for idx, unit in enumerate(work_units[:num_movements], 1):
            file_path = unit.get('file', '')
            if not file_path:
                print(f"  Movement {idx}: No file path found")
                failed.append(f"Sonata {sonata_num}, movement {idx}")
                continue
            
            output_file = OUTPUT_DIR / f"{sonata_num}-{idx}.mei"
            
            if output_file.exists():
                print(f"  Movement {idx} ({unit.get('unit', '?')}): Already exists, skipping")
                skipped += 1
                continue
            
            print(f"  Movement {idx} ({unit.get('unit', '?')}): Downloading from {file_path}")
            
            success = download_mei_file(session, file_path, output_file)
            
            if success:
                downloaded += 1
                file_size = output_file.stat().st_size
                print(f"    ✓ Downloaded successfully ({file_size:,} bytes)")
            else:
                failed.append(f"Sonata {sonata_num}, movement {idx}")
                print(f"    ✗ Failed to download")
            
            time.sleep(0.5)  # Be polite to the server
        
        print()  # Blank line between sonatas
    
    # Summary
    print("="*60)
    print(f"Download complete!")
    print(f"  Successfully downloaded: {downloaded}")
    print(f"  Already existed: {skipped}")
    print(f"  Total: {downloaded + skipped}/{total_files}")
    
    if failed:
        print(f"\n  Failed downloads ({len(failed)}):")
        for item in failed:
            print(f"    - {item}")
    
    print("="*60)


if __name__ == "__main__":
    main()

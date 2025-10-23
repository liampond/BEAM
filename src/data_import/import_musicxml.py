#!/usr/bin/env python3
"""
Download Mozart Piano Sonata MusicXML files from DCMLab GitHub repository.
Converts KV numbers to standard sonata numbering (01-18).

Source: https://github.com/DCMLab/schema_annotation_data
"""

import requests
from pathlib import Path
import time

# Base URL for raw GitHub content
BASE_URL = "https://raw.githubusercontent.com/DCMLab/schema_annotation_data/master/data/mozart_sonatas/musicxml"

# Output directory
OUTPUT_DIR = Path("data/musicxml")

# Mozart Piano Sonatas: KV number -> (sonata number, movement count)
SONATAS = {
    279: ('01', 3), 280: ('02', 3), 281: ('03', 3), 282: ('04', 3),
    283: ('05', 3), 284: ('06', 3), 309: ('07', 3), 310: ('08', 3),
    311: ('09', 3), 330: ('10', 3), 331: ('11', 3), 332: ('12', 3),
    333: ('13', 3), 457: ('14', 3), 533: ('15', 2), 545: ('16', 3),
    570: ('17', 3), 576: ('18', 3)
}

def download_file(url, output_path):
    """Download a file from URL to output_path"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Verify it's XML content (can start with <?xml or <!DOCTYPE)
        content = response.text.strip()
        if not (content.startswith('<?xml') or content.startswith('<!DOCTYPE')):
            print(f"    ⚠ Warning: File doesn't appear to be XML")
            return False
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        file_size = len(response.text)
        print(f"    ✓ Downloaded successfully ({file_size:,} bytes)")
        return True
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"    ✗ File not found (404)")
        else:
            print(f"    ✗ HTTP Error: {e}")
        return False
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading MusicXML files from DCMLab GitHub repository")
    print(f"Output directory: {OUTPUT_DIR.absolute()}\n")
    
    downloaded = 0
    skipped = 0
    failed = 0
    
    for kv, (sonata_num, movements) in SONATAS.items():
        print(f"Sonata {sonata_num} (KV {kv}):")
        
        for movement in range(1, movements + 1):
            # GitHub repo uses K{kv}-{movement}.xml format
            source_filename = f"K{kv}-{movement}.xml"
            # We save as {sonata_num}-{movement}.xml
            output_filename = f"{sonata_num}-{movement}.xml"
            output_path = OUTPUT_DIR / output_filename
            
            # Check if file already exists
            if output_path.exists():
                file_size = output_path.stat().st_size
                print(f"  Movement {movement}: Already exists ({file_size:,} bytes), skipping")
                skipped += 1
                continue
            
            # Download the file
            url = f"{BASE_URL}/{source_filename}"
            print(f"  Movement {movement}: Downloading {source_filename}...")
            
            if download_file(url, output_path):
                downloaded += 1
            else:
                failed += 1
            
            # Small delay to be respectful to GitHub
            time.sleep(0.3)
        
        print()
    
    print(f"\nDownload complete!")
    print(f"  Downloaded: {downloaded} files")
    print(f"  Skipped (already exist): {skipped} files")
    print(f"  Failed: {failed} files")
    print(f"  Total files: {downloaded + skipped} files")

if __name__ == "__main__":
    main()


import os
import sys
import sqlite3
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.core.extract_passage import extract

def main():
    db_path = Path(__file__).parent.parent / "benchmark.db"
    output_dir = Path(__file__).parent.parent / "passages"
    output_dir.mkdir(exist_ok=True)
    
    # Create subdirectories for each format
    for fmt in ['abc', 'humdrum', 'mei', 'musicxml']:
        (output_dir / fmt).mkdir(exist_ok=True)
    
    data_dir = Path(__file__).parent.parent / "data"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = """
        SELECT passage_id, sonata_number, movement, 
               start_measure_abc, end_measure_abc,
               start_measure_mei, end_measure_mei,
               start_measure_musicxml, end_measure_musicxml,
               start_measure_humdrum, end_measure_humdrum
        FROM passages
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    print(f"Found {len(rows)} passages in database.")
    
    for row in rows:
        p_id = row[0]
        sonata = row[1]
        movement = row[2]
        
        # Get Humdrum measures as fallback
        hum_start = row[9]
        hum_end = row[10]
        
        measures = {
            'abc': (row[3], row[4]),
            'mei': (row[5], row[6]),
            'musicxml': (row[7], row[8]),
            'humdrum': (row[9], row[10])
        }
        
        print(f"Processing {p_id} (Sonata {sonata}, Mvt {movement})...")
        
        for fmt, (start, end) in measures.items():
            # Use Humdrum fallback if measures are missing
            if (start is None or end is None) and (hum_start is not None and hum_end is not None):
                start, end = hum_start, hum_end
                
            if start is None or end is None:
                # print(f"  - {fmt}: Skipped (no measure range defined)")
                continue
                
            ext = {'musicxml': 'xml', 'abc': 'abc', 'mei': 'mei', 'humdrum': 'krn'}[fmt]
            
            if fmt == 'humdrum':
                src_path = data_dir / fmt / f"{sonata:02d}-{movement}.krn"
            elif fmt == 'musicxml':
                src_path = data_dir / fmt / f"{sonata:02d}-{movement}.xml"
            else:
                src_path = data_dir / fmt / f"{sonata:02d}-{movement}.{ext}"
            
            try:
                content = extract(fmt, str(src_path), start, end)
                output_path = output_dir / fmt / f"{p_id}.{ext}"
                with open(output_path, 'w') as f:
                    f.write(content)
                # print(f"  - {fmt}: Extracted to {output_path.name}")
            except Exception as e:
                print(f"  - {fmt}: FAILED ({e})")

if __name__ == "__main__":
    main()

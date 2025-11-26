
import sqlite3
from pathlib import Path

def update_passages():
    db_path = Path("benchmark.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Range P-055 to P-066
    passage_ids = [f"P-{i:03d}" for i in range(55, 67)]
    
    print(f"Checking passages {passage_ids[0]} to {passage_ids[-1]}...")
    
    for pid in passage_ids:
        # Get current state
        cursor.execute("""
            SELECT start_measure_humdrum, end_measure_humdrum,
                   verified_abc, verified_mei, verified_musicxml
            FROM passages WHERE passage_id = ?
        """, (pid,))
        row = cursor.fetchone()
        
        if not row:
            print(f"Passage {pid} not found.")
            continue
            
        hum_start, hum_end, v_abc, v_mei, v_mxl = row
        
        if hum_start is None or hum_end is None:
            print(f"Skipping {pid}: Humdrum measures not defined.")
            continue
            
        updates = []
        params = []
        
        if v_abc == 1:
            updates.append("start_measure_abc = ?, end_measure_abc = ?")
            params.extend([hum_start, hum_end])
            print(f"  - Updating ABC for {pid} to {hum_start}-{hum_end}")
            
        if v_mei == 1:
            updates.append("start_measure_mei = ?, end_measure_mei = ?")
            params.extend([hum_start, hum_end])
            print(f"  - Updating MEI for {pid} to {hum_start}-{hum_end}")
            
        if v_mxl == 1:
            updates.append("start_measure_musicxml = ?, end_measure_musicxml = ?")
            params.extend([hum_start, hum_end])
            print(f"  - Updating MusicXML for {pid} to {hum_start}-{hum_end}")
            
        if updates:
            query = f"UPDATE passages SET {', '.join(updates)} WHERE passage_id = ?"
            params.append(pid)
            cursor.execute(query, params)
            
    conn.commit()
    conn.close()
    print("Database update complete.")

if __name__ == "__main__":
    update_passages()

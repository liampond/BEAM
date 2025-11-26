
import sqlite3
import csv
import os
from pathlib import Path

def export_table_to_csv(cursor, table_name, output_dir):
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    # Get column names
    column_names = [description[0] for description in cursor.description]
    
    output_path = output_dir / f"{table_name}.csv"
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(column_names)
        writer.writerows(rows)
    
    print(f"Exported {table_name} to {output_path}")

def main():
    db_path = Path(__file__).parent.parent / "benchmark.db"
    output_dir = Path(__file__).parent.parent / "database_exports"
    output_dir.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table[0]
        export_table_to_csv(cursor, table_name, output_dir)
        
    conn.close()

if __name__ == "__main__":
    main()

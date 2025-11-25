#!/usr/bin/env python3
"""
Export database tables to CSV files.

Exports all tables from the benchmark database to CSV files in database_exports/.
Creates a summary file with row counts and metadata.
"""

import sqlite3
import csv
from pathlib import Path
from datetime import datetime

# Database and export paths
DB_PATH = Path(__file__).parent.parent.parent.parent / "benchmark.db"
EXPORT_DIR = Path(__file__).parent.parent.parent.parent / "database_exports"


def export_table_to_csv(conn, table_name, output_path):
    """Export a single table to CSV."""
    cursor = conn.cursor()
    
    # Get all rows
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    # Get column names
    column_names = [description[0] for description in cursor.description]
    
    # Write to CSV
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(column_names)
        writer.writerows(rows)
    
    return len(rows)


def create_summary(conn, export_dir):
    """Create a summary file with database statistics."""
    cursor = conn.cursor()
    
    # Get table counts
    cursor.execute("SELECT COUNT(*) FROM question_types")
    question_types_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM passages")
    passages_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions")
    questions_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM llm_responses")
    responses_count = cursor.fetchone()[0]
    
    # Get verified counts
    cursor.execute("SELECT COUNT(DISTINCT passage_id) FROM passages WHERE verified_abc = 1")
    verified_passages = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions WHERE verified_abc = 1")
    verified_questions_abc = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions WHERE verified_humdrum = 1")
    verified_questions_humdrum = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions WHERE verified_mei = 1")
    verified_questions_mei = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions WHERE verified_musicxml = 1")
    verified_questions_musicxml = cursor.fetchone()[0]
    
    # Write summary
    summary_path = export_dir / "database_summary.txt"
    with open(summary_path, 'w') as f:
        f.write("="*60 + "\n")
        f.write("DATABASE EXPORT SUMMARY\n")
        f.write("="*60 + "\n")
        f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Database: {DB_PATH}\n")
        f.write("\n")
        f.write("TABLE COUNTS:\n")
        f.write("-" * 60 + "\n")
        f.write(f"Question Types: {question_types_count}\n")
        f.write(f"Passages: {passages_count} ({verified_passages} verified)\n")
        f.write(f"Questions: {questions_count}\n")
        f.write(f"LLM Responses: {responses_count}\n")
        f.write("\n")
        f.write("VERIFIED ANSWERS BY FORMAT:\n")
        f.write("-" * 60 + "\n")
        f.write(f"ABC: {verified_questions_abc} questions\n")
        f.write(f"Humdrum: {verified_questions_humdrum} questions\n")
        f.write(f"MEI: {verified_questions_mei} questions\n")
        f.write(f"MusicXML: {verified_questions_musicxml} questions\n")
        f.write("="*60 + "\n")
    
    print(f"✓ Created summary: {summary_path}")


def main():
    """Export all database tables to CSV."""
    # Check if database exists
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        print("Run init_database.py first to create the database.")
        return
    
    # Create export directory
    EXPORT_DIR.mkdir(exist_ok=True)
    print(f"Exporting database to: {EXPORT_DIR}")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Export each table
        tables = ['question_types', 'passages', 'questions', 'llm_responses']
        
        for table in tables:
            output_path = EXPORT_DIR / f"{table}.csv"
            row_count = export_table_to_csv(conn, table, output_path)
            print(f"✓ Exported {table}: {row_count} rows → {output_path.name}")
        
        # Create summary
        create_summary(conn, EXPORT_DIR)
        
        print(f"\n✓ Export complete!")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()

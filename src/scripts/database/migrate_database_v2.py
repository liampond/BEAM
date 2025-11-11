#!/usr/bin/env python3
"""
Migrate database to version 2:
1. Add format-specific answer columns to questions table
2. Renumber passages: auto-generated passages first (P-001+), manual passages last
3. Renumber questions: auto-generated questions first (Q1+), manual questions last
4. Update all references in test_cases
"""

import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def backup_database(db_path: Path) -> Path:
    """Create a backup of the database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"benchmark_backup_{timestamp}.db"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Created backup: {backup_path}")
    return backup_path


def add_format_columns(conn: sqlite3.Connection):
    """Add format-specific answer columns to questions table."""
    cursor = conn.cursor()
    
    print("\n1. Adding format-specific answer columns...")
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(questions)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    
    columns_to_add = ['answer_abc', 'answer_mei', 'answer_musicxml', 'answer_humdrum']
    
    for col in columns_to_add:
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE questions ADD COLUMN {col} TEXT")
            print(f"  ✓ Added column: {col}")
        else:
            print(f"  ⊙ Column already exists: {col}")
    
    # Copy correct_answer to all format columns as default
    print("  • Copying correct_answer to all format columns...")
    cursor.execute("""
        UPDATE questions 
        SET answer_abc = correct_answer,
            answer_mei = correct_answer,
            answer_musicxml = correct_answer,
            answer_humdrum = correct_answer
    """)
    
    conn.commit()
    print("  ✓ Format-specific columns populated with default answers")


def create_passage_mapping(conn: sqlite3.Connection) -> dict:
    """
    Create mapping from old passage IDs to new passage IDs.
    Returns: {old_pid: new_pid}
    """
    cursor = conn.cursor()
    
    print("\n2. Creating passage ID mapping...")
    
    # Get all passages with their question info
    cursor.execute("""
        SELECT p.passage_id,
               SUM(CASE WHEN q.question_id >= 122 THEN 1 ELSE 0 END) as auto_count
        FROM passages p
        LEFT JOIN questions q ON p.passage_id = q.passage_id
        GROUP BY p.passage_id
        ORDER BY p.passage_id
    """)
    
    all_passages = cursor.fetchall()
    
    # Separate auto-generated vs manual-only passages
    auto_passages = [pid for pid, auto_count in all_passages if auto_count > 0]
    manual_passages = [pid for pid, auto_count in all_passages if auto_count == 0]
    
    # Create mapping
    mapping = {}
    
    # Auto-generated passages get P-001 through P-046
    for i, old_pid in enumerate(auto_passages, 1):
        mapping[old_pid] = i
    
    # Manual-only passages get P-047+
    for i, old_pid in enumerate(manual_passages, len(auto_passages) + 1):
        mapping[old_pid] = i
    
    print(f"  ✓ {len(auto_passages)} auto-generated passages → P-001 to P-{len(auto_passages):03d}")
    print(f"  ✓ {len(manual_passages)} manual-only passages → P-{len(auto_passages)+1:03d} to P-{len(all_passages):03d}")
    
    return mapping


def create_question_mapping(conn: sqlite3.Connection, passage_mapping: dict) -> dict:
    """
    Create mapping from old question IDs to new question IDs.
    Returns: {old_qid: new_qid}
    """
    cursor = conn.cursor()
    
    print("\n3. Creating question ID mapping...")
    
    # Identify which passages have auto-generated questions (new P-001 to P-046)
    auto_generated_passage_ids = {old_pid for old_pid, new_pid in passage_mapping.items() if new_pid <= 46}
    
    # Get all questions with their new passage IDs
    cursor.execute("SELECT question_id, passage_id FROM questions")
    all_questions = [(qid, pid, passage_mapping[pid]) for qid, pid in cursor.fetchall()]
    
    # Sort by: 1) auto/manual based on PASSAGE, 2) NEW passage ID, 3) old question ID
    all_questions.sort(key=lambda x: (
        0 if x[1] in auto_generated_passage_ids else 1,  # Auto-generated passages first
        x[2],  # New passage ID
        x[0]   # Original question ID
    ))
    
    # Create mapping
    mapping = {}
    for new_qid, (old_qid, old_pid, new_pid) in enumerate(all_questions, 1):
        mapping[old_qid] = new_qid
    
    # Count auto vs manual based on passage
    auto_count = sum(1 for old_qid, old_pid, _ in all_questions if old_pid in auto_generated_passage_ids)
    manual_count = len(all_questions) - auto_count
    
    print(f"  ✓ {auto_count} auto-generated questions → Q1 to Q{auto_count}")
    print(f"  ✓ {manual_count} manual questions → Q{auto_count+1} to Q{len(all_questions)}")
    
    return mapping


def apply_passage_renumbering(conn: sqlite3.Connection, mapping: dict):
    """Apply passage ID renumbering."""
    cursor = conn.cursor()
    
    print("\n4. Renumbering passages...")
    
    # Create temporary table for new passage IDs
    cursor.execute("""
        CREATE TEMPORARY TABLE passage_mapping (
            old_id INTEGER PRIMARY KEY,
            new_id INTEGER
        )
    """)
    
    for old_id, new_id in mapping.items():
        cursor.execute("INSERT INTO passage_mapping VALUES (?, ?)", (old_id, new_id))
    
    # Create new passages table with renumbered IDs
    cursor.execute("""
        CREATE TABLE passages_new (
            passage_id INTEGER PRIMARY KEY,
            piece_id INTEGER NOT NULL,
            granularity TEXT NOT NULL,
            start_measure INTEGER,
            end_measure INTEGER,
            description TEXT,
            num_measures INTEGER,
            FOREIGN KEY (piece_id) REFERENCES pieces(piece_id)
        )
    """)
    
    # Copy data with new IDs
    cursor.execute("""
        INSERT INTO passages_new 
        SELECT pm.new_id, p.piece_id, p.granularity, p.start_measure, p.end_measure,
               p.description, p.num_measures
        FROM passages p
        JOIN passage_mapping pm ON p.passage_id = pm.old_id
    """)
    
    # Update questions to reference new passage IDs
    cursor.execute("""
        UPDATE questions
        SET passage_id = (SELECT new_id FROM passage_mapping WHERE old_id = passage_id)
    """)
    
    # Drop old passages table and rename new one
    cursor.execute("DROP TABLE passages")
    cursor.execute("ALTER TABLE passages_new RENAME TO passages")
    
    conn.commit()
    print("  ✓ Passage IDs updated in passages and questions tables")


def apply_question_renumbering(conn: sqlite3.Connection, mapping: dict):
    """Apply question ID renumbering."""
    cursor = conn.cursor()
    
    print("\n5. Renumbering questions...")
    
    # Create temporary table for new question IDs
    cursor.execute("""
        CREATE TEMPORARY TABLE question_mapping (
            old_id INTEGER PRIMARY KEY,
            new_id INTEGER
        )
    """)
    
    for old_id, new_id in mapping.items():
        cursor.execute("INSERT INTO question_mapping VALUES (?, ?)", (old_id, new_id))
    
    # Create new questions table with renumbered IDs
    cursor.execute("""
        CREATE TABLE questions_new (
            question_id INTEGER PRIMARY KEY,
            passage_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            correct_answer TEXT,
            difficulty TEXT,
            question_type TEXT,
            answer_abc TEXT,
            answer_mei TEXT,
            answer_musicxml TEXT,
            answer_humdrum TEXT,
            FOREIGN KEY (passage_id) REFERENCES passages(passage_id)
        )
    """)
    
    # Copy data with new IDs
    cursor.execute("""
        INSERT INTO questions_new 
        SELECT qm.new_id, q.passage_id, q.question_text, q.correct_answer,
               q.difficulty, q.question_type, 
               q.answer_abc, q.answer_mei, q.answer_musicxml, q.answer_humdrum
        FROM questions q
        JOIN question_mapping qm ON q.question_id = qm.old_id
    """)
    
    # Create new test_cases table with renumbered question IDs
    cursor.execute("""
        CREATE TABLE test_cases_new (
            test_case_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            encoding_id INTEGER NOT NULL,
            FOREIGN KEY (question_id) REFERENCES questions(question_id),
            FOREIGN KEY (encoding_id) REFERENCES encodings(encoding_id)
        )
    """)
    
    # Copy test_cases with new question IDs
    cursor.execute("""
        INSERT INTO test_cases_new (question_id, encoding_id)
        SELECT qm.new_id, tc.encoding_id
        FROM test_cases tc
        JOIN question_mapping qm ON tc.question_id = qm.old_id
    """)
    
    # Drop old tables and rename new ones
    cursor.execute("DROP TABLE questions")
    cursor.execute("ALTER TABLE questions_new RENAME TO questions")
    cursor.execute("DROP TABLE test_cases")
    cursor.execute("ALTER TABLE test_cases_new RENAME TO test_cases")
    
    conn.commit()
    print("  ✓ Question IDs updated in questions and test_cases tables")


def verify_migration(conn: sqlite3.Connection):
    """Verify the migration was successful."""
    cursor = conn.cursor()
    
    print("\n6. Verifying migration...")
    
    # Check format columns exist and are populated
    cursor.execute("""
        SELECT COUNT(*) 
        FROM questions 
        WHERE answer_abc IS NOT NULL 
          AND answer_mei IS NOT NULL 
          AND answer_musicxml IS NOT NULL 
          AND answer_humdrum IS NOT NULL
    """)
    count = cursor.fetchone()[0]
    print(f"  ✓ {count} questions have all format-specific answers")
    
    # Check passage renumbering
    cursor.execute("SELECT MIN(passage_id), MAX(passage_id) FROM passages")
    min_pid, max_pid = cursor.fetchone()
    print(f"  ✓ Passage IDs now range from {min_pid} to {max_pid}")
    
    # Check question renumbering
    cursor.execute("SELECT MIN(question_id), MAX(question_id) FROM questions")
    min_qid, max_qid = cursor.fetchone()
    print(f"  ✓ Question IDs now range from {min_qid} to {max_qid}")
    
    # Check test_cases still reference valid questions
    cursor.execute("""
        SELECT COUNT(*)
        FROM test_cases tc
        LEFT JOIN questions q ON tc.question_id = q.question_id
        WHERE q.question_id IS NULL
    """)
    orphaned = cursor.fetchone()[0]
    if orphaned == 0:
        print(f"  ✓ All test_cases reference valid questions")
    else:
        print(f"  ⚠ WARNING: {orphaned} test_cases reference non-existent questions!")
    
    # Show sample of new numbering
    print("\n  Sample passages (first 5 with auto-generated questions):")
    cursor.execute("""
        SELECT p.passage_id, pc.sonata_number, pc.movement, 
               p.start_measure, p.end_measure,
               COUNT(q.question_id) as q_count,
               MIN(q.question_id) as first_q,
               MAX(q.question_id) as last_q
        FROM passages p
        JOIN pieces pc ON p.piece_id = pc.piece_id
        JOIN questions q ON p.passage_id = q.passage_id
        GROUP BY p.passage_id
        ORDER BY p.passage_id
        LIMIT 5
    """)
    for row in cursor.fetchall():
        pid, sonata, mov, start, end, q_count, first_q, last_q = row
        print(f"    P-{pid:03d}: Sonata {sonata}, Mvmt {mov}, M.{start}-{end} → {q_count} questions (Q{first_q}-Q{last_q})")


def main():
    """Run the migration."""
    db_path = Path(__file__).parent.parent.parent / "benchmark.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    print("="*80)
    print("DATABASE MIGRATION TO V2")
    print("="*80)
    print(f"Database: {db_path}")
    print()
    
    # Ask for confirmation
    response = input("This will modify the database. Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Migration cancelled.")
        sys.exit(0)
    
    # Create backup
    backup_path = backup_database(db_path)
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        
        # Perform migration steps
        add_format_columns(conn)
        passage_mapping = create_passage_mapping(conn)
        question_mapping = create_question_mapping(conn, passage_mapping)
        apply_passage_renumbering(conn, passage_mapping)
        apply_question_renumbering(conn, question_mapping)
        verify_migration(conn)
        
        conn.close()
        
        print("\n" + "="*80)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY")
        print("="*80)
        print(f"\nBackup saved to: {backup_path}")
        print("\nNext steps:")
        print("1. Test the database with existing scripts")
        print("2. Regenerate format-specific answers using validate_all_answers_cross_format.py")
        print("3. Update any hardcoded question/passage IDs in your code")
        
    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        print(f"\nRestoring from backup...")
        shutil.copy2(backup_path, db_path)
        print("Database restored.")
        sys.exit(1)


if __name__ == '__main__':
    main()

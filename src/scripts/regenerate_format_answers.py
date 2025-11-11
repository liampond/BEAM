#!/usr/bin/env python3
"""
Regenerate format-specific answers for all auto-generated questions.
This script analyzes each passage in each format and updates the database.
"""

import sys
from pathlib import Path
from typing import Dict, Optional
from tempfile import NamedTemporaryFile

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.db_utils import get_connection
from src.core.question_utils import get_auto_generated_passages
from src.core.extract_passage import extract
from src.core.passage_analysis import (
    MusicXMLAnalyzer,
    count_rests,
    select_first_note,
    select_last_note,
    select_lowest_note,
    count_pitch_classes,
    longest_note_duration_beats,
    format_pitch,
    format_beats,
)


def analyze_musicxml(musicxml_content: str, question_text: str) -> Optional[str]:
    """Analyze MusicXML and return answer to the question."""
    with NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(musicxml_content)
        temp_path = Path(f.name)
    
    try:
        analyzer = MusicXMLAnalyzer(temp_path)
        
        # Get all events
        all_events = []
        for measure_num in sorted(analyzer._measures.keys()):
            measure_data = analyzer.get_measure(measure_num)
            all_events.extend(measure_data.events)
        
        # Determine question type and calculate answer
        q_lower = question_text.lower()
        
        # Rest count
        if 'how many rests' in q_lower:
            return str(count_rests(all_events))
        
        # First note pitch (right hand = staff 1)
        if 'first note in the right hand' in q_lower or 'first note in the treble' in q_lower:
            note = select_first_note(all_events, staff=1)
            return format_pitch(note.step, note.alter, note.octave)
        
        # Last note pitch (right hand = staff 1)
        if 'last note in the right hand' in q_lower or 'last note in the treble' in q_lower:
            note = select_last_note(all_events, staff=1)
            return format_pitch(note.step, note.alter, note.octave)
        
        # Lowest note pitch (left hand = staff 2)
        if 'lowest note in the left hand' in q_lower or 'lowest note in the bass' in q_lower:
            note = select_lowest_note(all_events, staff=2)
            return format_pitch(note.step, note.alter, note.octave)
        
        # Longest note duration
        if 'duration of the longest' in q_lower:
            duration = longest_note_duration_beats(all_events)
            return format_beats(duration)
        
        # Pitch class count (left hand = staff 2)
        if 'pitch class' in q_lower and 'left hand' in q_lower:
            count = count_pitch_classes(all_events, staff=2)
            return str(count)
        
        return None
        
    finally:
        temp_path.unlink()


def regenerate_answers_for_passage(conn, passage_id: int, sonata: int, movement: int, 
                                   start_measure: int, end_measure: int):
    """Regenerate all format-specific answers for a passage."""
    data_dir = Path(__file__).parent.parent.parent / "data"
    
    # Get all questions for this passage
    cursor = conn.cursor()
    cursor.execute("""
        SELECT question_id, question_text, question_type
        FROM questions
        WHERE passage_id = ?
        ORDER BY question_id
    """, (passage_id,))
    
    questions = cursor.fetchall()
    
    if not questions:
        return
    
    print(f"  Processing P-{passage_id:03d}: {len(questions)} questions")
    
    # Extract passage in MusicXML format (most reliable)
    try:
        musicxml_file = data_dir / "musicxml" / f"{sonata:02d}-{movement}.xml"
        musicxml_content = extract('musicxml', str(musicxml_file), start_measure, end_measure)
    except Exception as e:
        print(f"    ❌ Error extracting MusicXML: {e}")
        return
    
    # Process each question
    updates = []
    for qid, qtext, qtype in questions:
        # For now, only regenerate melodic and rhythmic questions
        # Manual 'general' questions need human verification
        if qtype not in ['melodic', 'rhythmic']:
            continue
        
        try:
            answer = analyze_musicxml(musicxml_content, qtext)
            if answer:
                # For now, set all formats to the MusicXML answer
                # Later we can add format-specific analysis
                updates.append((answer, answer, answer, answer, qid))
        except Exception as e:
            print(f"    ⚠ Q-{qid:03d}: Error analyzing - {e}")
    
    # Update database
    if updates:
        cursor.executemany("""
            UPDATE questions
            SET answer_musicxml = ?, answer_abc = ?, answer_mei = ?, answer_humdrum = ?
            WHERE question_id = ?
        """, updates)
        conn.commit()
        print(f"    ✓ Updated {len(updates)} answers")


def main():
    """Regenerate all format-specific answers."""
    conn = get_connection()
    
    # Get all passages with auto-generated questions
    passage_ids = get_auto_generated_passages(conn)
    
    if not passage_ids:
        print("No passages found with auto-generated questions.")
        conn.close()
        return
    
    print(f"\n{'='*80}")
    print(f"REGENERATING FORMAT-SPECIFIC ANSWERS")
    print(f"{'='*80}")
    print(f"Total passages: {len(passage_ids)}\n")
    
    # Get passage details and regenerate
    cursor = conn.cursor()
    for i, pid in enumerate(passage_ids, 1):
        cursor.execute("""
            SELECT pc.sonata_number, pc.movement, p.start_measure, p.end_measure
            FROM passages p
            JOIN pieces pc ON p.piece_id = pc.piece_id
            WHERE p.passage_id = ?
        """, (pid,))
        
        row = cursor.fetchone()
        if row:
            sonata, movement, start, end = row
            print(f"[{i}/{len(passage_ids)}] P-{pid:03d}: Sonata {sonata}, Mvmt {movement}, M.{start}-{end}")
            regenerate_answers_for_passage(conn, pid, sonata, movement, start, end)
    
    conn.close()
    
    print(f"\n{'='*80}")
    print(f"✅ REGENERATION COMPLETE")
    print(f"{'='*80}")
    print(f"\nNext steps:")
    print(f"1. Review answers manually: PYTHONPATH=src .venv/bin/python -m cli.review_format musicxml")
    print(f"2. Then review other formats: abc, mei, humdrum")


if __name__ == '__main__':
    main()

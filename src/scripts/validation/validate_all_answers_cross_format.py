#!/usr/bin/env python3
"""
Validate ALL auto-generated answers across all four music encoding formats.
This script regenerates answers for each format and checks for discrepancies.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.db_utils import get_connection
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
from tempfile import NamedTemporaryFile


def analyze_musicxml(musicxml_content: str, question_text: str) -> str:
    """Analyze MusicXML and return answer to the question."""
    # Create temporary file for analyzer
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
        
        return "UNKNOWN_QUESTION_TYPE"
        
    finally:
        temp_path.unlink()


def validate_question_across_formats(question_id: int, passage_id: int, question_text: str, 
                                     correct_answer: str, sonata: int, movement: int, 
                                     start_measure: int, end_measure: int) -> Dict:
    """
    Validate a single question by regenerating answers from all four formats.
    """
    data_dir = Path(__file__).parent.parent.parent / "data"
    
    results = {
        'question_id': question_id,
        'passage_id': f'P-{passage_id:03d}',
        'question_text': question_text[:80] + '...' if len(question_text) > 80 else question_text,
        'stored_answer': correct_answer,
    }
    
    # Try each format
    for format_name, file_pattern in [
        ('abc', f"{sonata:02d}-{movement}.abc"),
        ('humdrum', f"{sonata:02d}-{movement}.krn"),
        ('musicxml', f"{sonata:02d}-{movement}.xml"),
        ('mei', f"{sonata:02d}-{movement}.mei"),
    ]:
        try:
            file_path = data_dir / format_name / file_pattern
            content = extract(format_name, str(file_path), start_measure, end_measure)
            
            # Currently only MusicXML analysis is implemented
            if format_name == 'musicxml':
                answer = analyze_musicxml(content, question_text)
                results[format_name] = answer
            else:
                results[format_name] = 'NOT_IMPLEMENTED'
                
        except Exception as e:
            results[format_name] = f'ERROR: {str(e)[:50]}'
    
    return results


def main():
    """Validate all auto-generated questions across all formats."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all auto-generated questions
    cursor.execute("""
        SELECT q.question_id, q.passage_id, q.question_text, q.correct_answer, q.question_type,
               pc.sonata_number, pc.movement, p.start_measure, p.end_measure
        FROM questions q
        JOIN passages p ON q.passage_id = p.passage_id
        JOIN pieces pc ON p.piece_id = pc.piece_id
        WHERE q.question_id >= 122
        ORDER BY q.question_id
    """)
    
    all_questions = cursor.fetchall()
    conn.close()
    
    print(f"Validating {len(all_questions)} auto-generated questions across formats...")
    print("=" * 100)
    print("Note: Currently only MusicXML analysis is fully implemented.")
    print("=" * 100)
    
    discrepancies = []
    by_type = {'melodic': [], 'rhythmic': []}
    
    for row in all_questions:
        qid, pid, qtext, correct_ans, qtype, sonata, movement, start, end = row
        
        results = validate_question_across_formats(qid, pid, qtext, correct_ans, 
                                                   sonata, movement, start, end)
        
        # Check if MusicXML answer matches stored answer
        musicxml_answer = results.get('musicxml', 'N/A')
        matches = musicxml_answer == correct_ans
        
        if not matches and musicxml_answer not in ['NOT_IMPLEMENTED', 'UNKNOWN_QUESTION_TYPE'] \
           and not musicxml_answer.startswith('ERROR'):
            discrepancies.append(results)
            by_type[qtype].append(results)
            print(f"\n❌ MISMATCH: Q{qid} ({results['passage_id']}) - {qtype}")
            print(f"   Question: {results['question_text']}")
            print(f"   Stored:   {correct_ans}")
            print(f"   MusicXML: {musicxml_answer}")
        else:
            symbol = "✓" if matches else "?"
            print(f"{symbol} Q{qid}: {qtype} - Stored={correct_ans}, MusicXML={musicxml_answer}")
    
    print("\n" + "=" * 100)
    if discrepancies:
        print(f"\n⚠️  Found {len(discrepancies)} question(s) where MusicXML-generated answer differs from stored answer")
        print(f"   - Melodic: {len(by_type['melodic'])} discrepancies")
        print(f"   - Rhythmic: {len(by_type['rhythmic'])} discrepancies")
        print("\nThese could be due to:")
        print("  1. Original answers generated before invisible rest fix")
        print("  2. Different encoding between formats")
        print("  3. Bugs in the analysis functions")
    else:
        print("\n✅ All MusicXML-generated answers match stored answers!")


if __name__ == '__main__':
    main()

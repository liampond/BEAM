"""
MusicXML Answer Extraction

Provides programmatic answer extraction from MusicXML files.

Available Extractors:
    - count_notes_in_staff: Count notes in upper/lower staff
    - count_rests: Count rests in passage
    - count_specific_note_types: Count specific note durations (e.g., sixteenth notes)
    - first_note_pitch: Get pitch of first note (highest if simultaneous)
    - first_note_duration: Get duration of first note as named value
    - extreme_pitches: Get highest or lowest note in staff
    - intervals: Calculate interval between first and last notes
    - longest_note_duration: Get duration of longest note in beats
    - pitch_class_count: Count unique pitch classes

All extractors follow the signature:
    extract_answer(file_path: str, passage_id: str, **kwargs) -> str

Example:
    from src.answer_extraction.musicxml import count_notes_in_staff
    
    answer = count_notes_in_staff.extract_answer(
        file_path='data/musicxml/16-1.xml',
        passage_id='P-001',
        staff='upper'
    )
    print(answer)  # "8"
"""

from . import _helpers
from . import count_notes_in_staff
from . import count_rests
from . import count_specific_note_types
from . import first_note_pitch
from . import first_note_duration
from . import extreme_pitches
from . import intervals
from . import longest_note_duration
from . import pitch_class_count

__all__ = [
    '_helpers',
    'count_notes_in_staff',
    'count_rests',
    'count_specific_note_types',
    'first_note_pitch',
    'first_note_duration',
    'extreme_pitches',
    'intervals',
    'longest_note_duration',
    'pitch_class_count',
]

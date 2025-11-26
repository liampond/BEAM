"""
MusicXML extractors.

Each module in this package extracts the answer to a specific question type
from MusicXML files.
"""

# Import all extractors to register them
from . import (
    q1_note_count_lower,
    q2_note_count_upper,
    q3_first_pitch_upper,
    q4_lowest_pitch_lower,
    q5_longest_duration,
    q6_pitch_class_count,
    q7_interval_first_last,
    q8_rest_count,
    q9_first_note_duration,
)

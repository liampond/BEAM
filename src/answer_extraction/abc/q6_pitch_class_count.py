"""
Q6: How many different pitch classes are used in the lower staff?

Consider pitch classes without regard to octave (i.e., all Cs are the same
pitch class). Enharmonic spellings are distinct pitch classes (F# and Gb
are counted separately). Grace notes are included.
"""

import re
from typing import Set
from ..registry import register_extractor
from .utils import (
    get_lower_staff_voices,
    extract_voice_content,
    parse_key_signature,
    extract_all_pitches_from_content,
)


@register_extractor(6, "abc")
def extract(file_path: str) -> str:
    """
    Count distinct pitch classes in the lower staff of an ABC notation file.

    Enharmonic spellings (e.g., F# vs Gb) are treated as distinct pitch classes,
    matching the MusicXML extractor and the Phase 6 prompt clarification.
    """
    with open(file_path, 'r') as f:
        content = f.read()

    key_sig = parse_key_signature(content)

    lower_voices = get_lower_staff_voices(content)

    all_pitches = []
    for voice_num in lower_voices:
        voice_content = extract_voice_content(content, voice_num)
        pitches = extract_all_pitches_from_content(voice_content, key_sig)
        all_pitches.extend(pitches)

    if not all_pitches:
        return "N/A"

    # Strip octave to get pitch class string ("F#5" -> "F#", "Gb3" -> "Gb").
    # F# and Gb remain distinct.
    pitch_classes: Set[str] = set()
    for pitch in all_pitches:
        m = re.match(r'([A-G][#b]{0,2})', pitch)
        if m:
            pitch_classes.add(m.group(1))

    return str(len(pitch_classes))

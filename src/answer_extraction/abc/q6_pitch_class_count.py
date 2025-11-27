"""
Q6: How many different pitch classes are used in the lower staff?

Consider pitch classes without regard to octave (i.e., all Cs are the same 
pitch class). Respond with a number (e.g., 5).

Pitch classes are normalized to MIDI pitch class (0-11), so enharmonic 
equivalents like Eb and D# are treated as the same pitch class.
Grace notes are included.
"""

from typing import Set
from ..registry import register_extractor
from ..core.pitch import pitch_to_midi, midi_to_pitch_class
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
    
    Pitch classes are determined by MIDI pitch mod 12, so enharmonic equivalents
    (e.g., Eb and D#) are treated as the same pitch class.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The count as a string
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    key_sig = parse_key_signature(content)
    
    # Get lower staff voices
    lower_voices = get_lower_staff_voices(content)
    
    # Collect all pitches from all lower staff voices
    all_pitches = []
    for voice_num in lower_voices:
        voice_content = extract_voice_content(content, voice_num)
        pitches = extract_all_pitches_from_content(voice_content, key_sig)
        all_pitches.extend(pitches)
    
    if not all_pitches:
        return "N/A"
    
    # Convert to MIDI pitch classes (0-11) to handle enharmonic equivalence
    pitch_classes: Set[int] = set()
    for pitch in all_pitches:
        midi_num = pitch_to_midi(pitch)
        pitch_class = midi_to_pitch_class(midi_num)
        pitch_classes.add(pitch_class)
    
    return str(len(pitch_classes))

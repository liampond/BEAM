"""ABC format parser.

Extracts musical signatures from ABC notation files with time-ordered events.

ABC is a text-based music notation format. This parser handles:
- Header fields (L: for note length, K: for key signature)
- Voice labels ([V:1], [V:2])
- Interleaved and grouped voice formats
- Accidental persistence within measures
- Key signature application
- Chords (bracket notation [CEG])
- Duration multipliers (C4 = 4x default length)
- Grace notes (braces {}) - excluded from signature
- Inline markers and tuplets
"""

from pathlib import Path
from typing import Optional, List, Dict, Tuple
import re

from .base import FormatParser
from ..signature import MusicalSignature, Event


class ABCParser(FormatParser):
    """Parser for ABC notation (.abc) files."""
    
    name = "ABC"
    file_extensions = ('.abc',)
    
    def extract_signature(
        self,
        file_path: Path,
        start_measure: int,
        end_measure: int,
        **kwargs
    ) -> Optional[MusicalSignature]:
        """Extract time-ordered musical signature from ABC file.
        
        Args:
            file_path: Path to .abc file
            start_measure: First measure to extract (1-indexed)
            end_measure: Last measure to extract (inclusive)
            **kwargs: Not used for ABC
        
        Returns:
            MusicalSignature with events sorted by (onset, pitch)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"ABC file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Extract default note length from header (L: field)
        default_length = self._extract_default_length(lines)
        
        # Extract key signature (K: field)
        key_signature = self._extract_key_signature(lines)
        
        # Find body start (after K: field)
        body_start = self._find_body_start(lines)
        body_lines = lines[body_start:]
        
        # Extract measures from body
        measures = self._extract_measures(body_lines)
        
        if not measures:
            return None
        
        # Validate measure range
        if start_measure < 1 or start_measure > len(measures):
            return None
        if end_measure < start_measure or end_measure > len(measures):
            return None
        
        # Extract target measures (convert to 0-indexed)
        target_measures = measures[start_measure - 1:end_measure]
        
        # Extract events with time information
        events = self._extract_events(
            measures=target_measures,
            default_length=default_length,
            key_signature=key_signature
        )
        
        if not events:
            return None
        
        measure_count = end_measure - start_measure + 1
        
        # Calculate total duration from events
        if events:
            max_offset_end = max(e.onset + e.duration for e in events)
            total_duration = max_offset_end
        else:
            total_duration = 0.0
        
        return MusicalSignature(
            events=events,
            measure_count=measure_count,
            total_duration=total_duration
        )
    
    def _extract_default_length(self, lines: List[str]) -> float:
        """Extract default note length from L: header field.
        
        Returns duration in quarter notes (1.0 = quarter note).
        """
        for line in lines:
            if line.startswith('L:'):
                # Parse L: 1/8, L: 1/16, etc.
                parts = line.split(':')[1].strip().split('/')
                if len(parts) == 2:
                    try:
                        numerator = int(parts[0])
                        denominator = int(parts[1])
                        # Convert to quarter note units
                        # L: 1/8 means eighth note = 0.5 quarter notes
                        # L: 1/16 means sixteenth note = 0.25 quarter notes
                        return (numerator / denominator) * 4.0
                    except ValueError:
                        pass
        # Default to sixteenth note if not specified
        return 0.25
    
    def _extract_key_signature(self, lines: List[str]) -> Dict[str, int]:
        """Extract key signature accidentals from K: header field.
        
        Returns dict mapping pitch class (lowercase) to accidental offset.
        """
        for line in lines:
            if line.startswith('K:'):
                # Parse K: D, K: Am, etc.
                key_str = line.split(':')[1].strip()
                # Remove extra info after key (like "clef=bass")
                key_str = key_str.split()[0] if key_str else ''
                return self._get_key_signature_accidentals(key_str)
        return {}
    
    def _find_body_start(self, lines: List[str]) -> int:
        """Find the line where the body starts (after K: field)."""
        for i, line in enumerate(lines):
            if line.startswith('K:'):
                return i + 1
        return 0
    
    def _extract_measures(self, body_lines: List[str]) -> List[Dict[str, str]]:
        """Extract measures from body lines.
        
        ABC files can have two formats:
        1. Interleaved: [V:1] content | [V:2] content | [V:1] content | [V:2] content |
        2. Grouped: All [V:1] measures, then all [V:2] measures
        
        Returns:
            List of measure dicts with 'v1', 'v2', and 'number' keys
        """
        measures = []
        current_measure = {'v1': '', 'v2': '', 'number': 0}
        measure_number = 0
        
        for line in body_lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('[V:1]'):
                # Check if this is a new measure (has barline |)
                if '|' in line:
                    # Save previous measure if complete
                    if current_measure['v1'] and current_measure['v2']:
                        measures.append(current_measure)
                    # Start new measure
                    measure_number += 1
                    current_measure = {'v1': line, 'v2': '', 'number': measure_number}
                else:
                    # Continuation of current V:1
                    current_measure['v1'] += ' ' + line
            elif line.startswith('[V:2]'):
                # Add V:2 content to current measure
                current_measure['v2'] += ' ' + line
        
        # Don't forget last measure
        if current_measure['v1'] and current_measure['v2']:
            measures.append(current_measure)
        
        return measures
    
    def _extract_events(
        self,
        measures: List[Dict[str, str]],
        default_length: float,
        key_signature: Dict[str, int]
    ) -> List[Event]:
        """Extract time-ordered events from measures.
        
        For now, we extract in the same order as the old implementation:
        all V:1 notes, then all V:2 notes per measure. This matches
        the old behavior for validation.
        
        Args:
            measures: List of measure dicts with v1/v2 content
            default_length: Base note duration in quarter notes
            key_signature: Key signature accidentals
        
        Returns:
            List of Event objects (will be sorted by onset, pitch later)
        """
        events = []
        current_onset = 0.0  # Simple incrementing onset for ordering
        
        for measure in measures:
            # Process V:1 (RH) first, then V:2 (LH) - matches old order
            for voice_num, voice_key in enumerate(['v1', 'v2'], start=1):
                content = measure[voice_key]
                
                # Clean up content
                content = self._clean_content(content)
                
                # Track accidentals within this measure
                # Initialize with key signature
                measure_accidentals = key_signature.copy()
                
                # Extract pitches and durations (old-style)
                pitches, durations = self._extract_pitches_and_durations(
                    content=content,
                    default_length=default_length,
                    measure_accidentals=measure_accidentals
                )
                
                # Create events with sequential onsets
                for pitch, duration in zip(pitches, durations):
                    events.append(Event(
                        onset=current_onset,
                        pitch=pitch,
                        duration=duration,
                        voice=voice_num,
                        is_grace=False
                    ))
                    current_onset += 0.001  # Tiny increment to preserve order
        
        return events
    
    def _clean_content(self, content: str) -> str:
        """Clean ABC content by removing markers."""
        # Remove grace notes (in braces {})
        content = re.sub(r'\{[^}]*\}', '', content)
        
        # Remove inline clef/key changes like [K:clef=treble]
        content = re.sub(r'\[K:[^\]]*\]', '', content)
        
        # Remove voice markers [V:1], [V:2]
        content = re.sub(r'\[V:\d+\]', '', content)
        
        # Remove tuplet markers like (3
        content = re.sub(r'\(\d+', '', content)
        
        # Remove barlines for simpler parsing
        content = content.replace('|', ' ')
        
        return content
    
    def _extract_pitches_and_durations(
        self,
        content: str,
        default_length: float,
        measure_accidentals: Dict[str, int]
    ) -> Tuple[List[int], List[float]]:
        """Extract pitches and durations from voice content.
        
        This matches the old implementation's extraction logic exactly.
        
        Args:
            content: Cleaned ABC content
            default_length: Base note duration
            measure_accidentals: Current accidentals (modified in place)
        
        Returns:
            (pitches, durations) tuple
        """
        pitches = []
        durations = []
        
        # Handle multiple voices within a staff (separated by &)
        voice_parts = content.split('&')
        
        for part in voice_parts:
            # Extract chords first - in brackets like [C4E4G4]
            chord_matches = re.findall(r'\[([^\]]+)\]', part)
            for chord_content in chord_matches:
                # Extract duration from first note
                duration_match = re.search(r'(\d+)', chord_content)
                chord_duration = default_length
                if duration_match:
                    multiplier = int(duration_match.group(1))
                    chord_duration = default_length * multiplier
                
                # Parse notes in chord
                notes = re.findall(r'([_=\^]?)([A-Ga-g][,\']*)', chord_content)
                for accidental, pitch in notes:
                    if pitch and pitch not in 'zZxX':
                        # Apply/update accidentals
                        pitch_letter = pitch[0].lower()
                        if accidental:
                            if accidental == '^':
                                measure_accidentals[pitch_letter] = 1
                            elif accidental == '_':
                                measure_accidentals[pitch_letter] = -1
                            elif accidental == '=':
                                measure_accidentals[pitch_letter] = 0
                        elif pitch_letter in measure_accidentals:
                            # Use persisting accidental
                            accidental = {-1: '_', 0: '=', 1: '^'}[measure_accidentals[pitch_letter]]
                        
                        midi = self._abc_to_midi(accidental, pitch)
                        if midi is not None:
                            pitches.append(midi)
                            durations.append(chord_duration)
            
            # Extract individual notes (not in chords)
            # Remove chords first
            no_chords = re.sub(r'\[[^\]]+\]', '', part)
            
            # Find notes with duration multipliers
            note_matches = re.findall(r'([_=\^]?)([A-Ga-g][,\']*)(\d*)', no_chords)
            for accidental, pitch, duration_str in note_matches:
                if pitch and pitch not in 'zZxX':
                    # Apply/update accidentals
                    pitch_letter = pitch[0].lower()
                    if accidental:
                        if accidental == '^':
                            measure_accidentals[pitch_letter] = 1
                        elif accidental == '_':
                            measure_accidentals[pitch_letter] = -1
                        elif accidental == '=':
                            measure_accidentals[pitch_letter] = 0
                    elif pitch_letter in measure_accidentals:
                        # Use persisting accidental
                        accidental = {-1: '_', 0: '=', 1: '^'}[measure_accidentals[pitch_letter]]
                    
                    midi = self._abc_to_midi(accidental, pitch)
                    if midi is not None:
                        pitches.append(midi)
                        # Parse duration
                        note_duration = default_length
                        if duration_str:
                            multiplier = int(duration_str)
                            note_duration = default_length * multiplier
                        durations.append(note_duration)
        
        return pitches, durations
    
    def _extract_voice_events(
        self,
        content: str,
        default_length: float,
        measure_accidentals: Dict[str, int],
        start_time: float,
        voice: int
    ) -> List[Event]:
        """Extract events from a single voice's content.
        
        Args:
            content: ABC content string (cleaned)
            default_length: Base note duration
            measure_accidentals: Current measure accidentals (modified in place)
            start_time: Starting time for this voice
            voice: Voice number (1 or 2)
        
        Returns:
            List of Event objects
        """
        events = []
        current_time = start_time
        
        # Handle multiple voices within a staff (separated by &)
        # Example: "D2A2C2 & x4B4" means two voices simultaneously
        voice_parts = content.split('&')
        
        for part in voice_parts:
            part_time = start_time
            
            # Extract chords first - chords are in brackets like [C4E4G4]
            chord_events, part = self._extract_chords(
                content=part,
                default_length=default_length,
                measure_accidentals=measure_accidentals,
                start_time=part_time,
                voice=voice
            )
            events.extend(chord_events)
            
            # Update time based on chord durations
            if chord_events:
                max_chord_end = max(e.onset + e.duration for e in chord_events)
                part_time = max(part_time, max_chord_end)
            
            # Extract individual notes
            note_events, final_time = self._extract_individual_notes(
                content=part,
                default_length=default_length,
                measure_accidentals=measure_accidentals,
                start_time=part_time,
                voice=voice
            )
            events.extend(note_events)
            
            # Update current_time
            current_time = max(current_time, final_time)
        
        return events
    
    def _extract_chords(
        self,
        content: str,
        default_length: float,
        measure_accidentals: Dict[str, int],
        start_time: float,
        voice: int
    ) -> Tuple[List[Event], str]:
        """Extract chord events and return remaining content.
        
        Returns:
            (events, content_without_chords)
        """
        events = []
        current_time = start_time
        
        # Find chords - chords are in brackets like [C4E4G4]
        chord_matches = re.finditer(r'\[([^\]]+)\]', content)
        
        for match in chord_matches:
            chord_content = match.group(1)
            
            # Extract duration multiplier from first note in chord
            duration_match = re.search(r'(\d+)', chord_content)
            chord_duration = default_length
            if duration_match:
                multiplier = int(duration_match.group(1))
                chord_duration = default_length * multiplier
            
            # Parse notes in chord
            notes = re.findall(r'([_=\^]?)([A-Ga-g][,\']*)', chord_content)
            
            for accidental, pitch in notes:
                if pitch and pitch not in 'zZxX':
                    # Apply/update accidentals
                    pitch_letter = pitch[0].lower()
                    accidental_value = self._parse_accidental(accidental, pitch_letter, measure_accidentals)
                    
                    # Convert to MIDI
                    midi = self._abc_to_midi(accidental, pitch)
                    if midi is not None:
                        events.append(Event(
                            onset=current_time,
                            pitch=midi,
                            duration=chord_duration,
                            voice=voice,
                            is_grace=False
                        ))
            
            current_time += chord_duration
        
        # Remove chords from content
        content_without_chords = re.sub(r'\[[^\]]+\]', '', content)
        
        return events, content_without_chords
    
    def _extract_individual_notes(
        self,
        content: str,
        default_length: float,
        measure_accidentals: Dict[str, int],
        start_time: float,
        voice: int
    ) -> Tuple[List[Event], float]:
        """Extract individual note events.
        
        Returns:
            (events, final_time)
        """
        events = []
        current_time = start_time
        
        # Find notes with duration multipliers
        # Pattern: optional accidental + pitch letter + optional octave markers + optional duration
        note_matches = re.findall(r'([_=\^]?)([A-Ga-g][,\']*)(\d*)', content)
        
        for accidental, pitch, duration_str in note_matches:
            if pitch and pitch not in 'zZxX':
                # Apply/update accidentals
                pitch_letter = pitch[0].lower()
                accidental_value = self._parse_accidental(accidental, pitch_letter, measure_accidentals)
                
                # Convert to MIDI
                midi = self._abc_to_midi(accidental, pitch)
                if midi is not None:
                    # Parse duration
                    note_duration = default_length
                    if duration_str:
                        multiplier = int(duration_str)
                        note_duration = default_length * multiplier
                    
                    events.append(Event(
                        onset=current_time,
                        pitch=midi,
                        duration=note_duration,
                        voice=voice,
                        is_grace=False
                    ))
                    
                    current_time += note_duration
        
        return events, current_time
    
    def _parse_accidental(
        self,
        accidental: str,
        pitch_letter: str,
        measure_accidentals: Dict[str, int]
    ) -> int:
        """Parse accidental and update measure state.
        
        Returns:
            Accidental value (-1, 0, 1)
        """
        if accidental:
            # Explicit accidental - update the measure state
            if accidental == '^':
                measure_accidentals[pitch_letter] = 1
                return 1
            elif accidental == '_':
                measure_accidentals[pitch_letter] = -1
                return -1
            elif accidental == '=':
                measure_accidentals[pitch_letter] = 0
                return 0
        elif pitch_letter in measure_accidentals:
            # No explicit accidental, but one was set earlier in measure
            return measure_accidentals[pitch_letter]
        
        return 0
    
    def _get_key_signature_accidentals(self, key_str: str) -> Dict[str, int]:
        """Get accidentals defined by a key signature.
        
        Args:
            key_str: ABC key signature string (e.g., 'D', 'Am', 'Bb')
        
        Returns:
            Dictionary mapping pitch class (lowercase) to accidental offset
        """
        # Key signature mappings
        key_signatures = {
            # Major keys with sharps
            'G': ['f'],
            'D': ['f', 'c'],
            'A': ['f', 'c', 'g'],
            'E': ['f', 'c', 'g', 'd'],
            'B': ['f', 'c', 'g', 'd', 'a'],
            'F#': ['f', 'c', 'g', 'd', 'a', 'e'],
            'C#': ['f', 'c', 'g', 'd', 'a', 'e', 'b'],
            # Major keys with flats
            'F': ['b'],
            'Bb': ['b', 'e'],
            'Eb': ['b', 'e', 'a'],
            'Ab': ['b', 'e', 'a', 'd'],
            'Db': ['b', 'e', 'a', 'd', 'g'],
            'Gb': ['b', 'e', 'a', 'd', 'g', 'c'],
            'Cb': ['b', 'e', 'a', 'd', 'g', 'c', 'f'],
            # Minor keys with sharps
            'Em': ['f'],
            'Bm': ['f', 'c'],
            'F#m': ['f', 'c', 'g'],
            'C#m': ['f', 'c', 'g', 'd'],
            'G#m': ['f', 'c', 'g', 'd', 'a'],
            'D#m': ['f', 'c', 'g', 'd', 'a', 'e'],
            'A#m': ['f', 'c', 'g', 'd', 'a', 'e', 'b'],
            # Minor keys with flats
            'Dm': ['b'],
            'Gm': ['b', 'e'],
            'Cm': ['b', 'e', 'a'],
            'Fm': ['b', 'e', 'a', 'd'],
            'Bbm': ['b', 'e', 'a', 'd', 'g'],
            'Ebm': ['b', 'e', 'a', 'd', 'g', 'c'],
            'Abm': ['b', 'e', 'a', 'd', 'g', 'c', 'f'],
            # No accidentals
            'C': [],
            'Am': [],
        }
        
        if key_str not in key_signatures:
            return {}
        
        accidentals_list = key_signatures[key_str]
        if not accidentals_list:
            return {}
        
        # Determine if sharps or flats
        sharp_keys = ['G', 'D', 'A', 'E', 'B', 'F#', 'C#',
                      'Em', 'Bm', 'F#m', 'C#m', 'G#m', 'D#m', 'A#m']
        
        accidental_value = 1 if key_str in sharp_keys else -1
        
        return {note: accidental_value for note in accidentals_list}
    
    def _abc_to_midi(self, accidental: str, note: str) -> Optional[int]:
        """Convert ABC note to MIDI number.
        
        Args:
            accidental: Accidental string ('_', '^', '=', or '')
            note: Pitch with octave markers (e.g., 'C', 'c', "c'", 'C,')
        
        Returns:
            MIDI note number or None
        """
        # Parse accidental
        accidental_value = 0
        if accidental == '_':
            accidental_value = -1
        elif accidental == '^':
            accidental_value = 1
        elif accidental == '=':
            accidental_value = 0
        
        if not note:
            return None
        
        pitch_letter = note[0]
        rest = note[1:]
        
        # Determine octave
        # ABC standard: C=C4 (uppercase), c=C5 (lowercase)
        if pitch_letter.isupper():
            octave = 4  # Uppercase base octave
        else:
            octave = 5  # Lowercase base octave
        
        octave += rest.count("'")  # Apostrophe raises octave
        octave -= rest.count(',')   # Comma lowers octave
        
        # Convert to MIDI
        pitch_classes = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
        pitch_class = pitch_classes[pitch_letter.lower()]
        midi = (octave + 1) * 12 + pitch_class + accidental_value
        
        return midi

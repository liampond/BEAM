"""Humdrum format parser.

Extracts musical signatures from Humdrum (.krn) files with time-ordered events.

Humdrum is a column-based format where each spine represents a musical voice.
This parser handles:
- Spine tracking (staff1/staff2 mapping)
- Spine manipulations (*^ for split, *v for join)
- Grace note detection (q/qq markers)
- Chord notation (space-separated pitches)
- Duration calculation (reciprocal notation: 4=quarter, 8=eighth)
- Measure number offsets
"""

from pathlib import Path
from typing import Optional, List, Dict
import re

from .base import FormatParser
from ..signature import MusicalSignature, Event


class HumdrumParser(FormatParser):
    """Parser for Humdrum (.krn) files."""
    
    name = "Humdrum"
    file_extensions = ('.krn',)
    
    def extract_signature(
        self,
        file_path: Path,
        start_measure: int,
        end_measure: int,
        **kwargs
    ) -> Optional[MusicalSignature]:
        """Extract time-ordered musical signature from Humdrum file.
        
        Args:
            file_path: Path to .krn file
            start_measure: First measure to extract (1-indexed)
            end_measure: Last measure to extract (inclusive)
            **kwargs: Not used for Humdrum
        
        Returns:
            MusicalSignature with events sorted by (onset, pitch)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Humdrum file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Find **kern spines (ignore **dynam and other non-note spines)
        kern_columns = self._find_kern_columns(lines)
        if not kern_columns:
            kern_columns = [0, 1]  # Fallback to first two columns
        
        # Track staff assignments (staff1=RH, staff2=LH for piano)
        staff_mapping = self._extract_staff_mapping(lines)
        
        # Get measure number offset
        offset = self._get_measure_offset(lines)
        target_start = start_measure + offset - 1
        target_end = end_measure + offset - 1
        
        # Extract events with time information
        events = self._extract_events(
            lines=lines,
            kern_columns=kern_columns,
            staff_mapping=staff_mapping,
            target_start=target_start,
            target_end=target_end
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
    
    def _find_kern_columns(self, lines: List[str]) -> List[int]:
        """Find which columns contain **kern spines."""
        for line in lines:
            if line.startswith('**'):
                tokens = line.strip().split('\t')
                return [i for i, token in enumerate(tokens) if token == '**kern']
        return []
    
    def _extract_staff_mapping(self, lines: List[str]) -> Dict[int, str]:
        """Extract staff assignments (staff1=RH, staff2=LH for piano)."""
        staff_mapping = {}
        for line in lines:
            if line.startswith('*staff'):
                tokens = line.strip().split('\t')
                for i, token in enumerate(tokens):
                    if token.startswith('*staff'):
                        staff_mapping[i] = token
                break
        return staff_mapping
    
    def _get_measure_offset(self, lines: List[str]) -> int:
        """Get the measure number offset (first measure number in file)."""
        for line in lines:
            if not line.startswith('='):
                continue
            token = line.split('\t', 1)[0][1:].rstrip('-').split()[0]
            if token and token.isdigit():
                value = int(token)
                return value if value != 0 else 0
        return 1
    
    def _extract_events(
        self,
        lines: List[str],
        kern_columns: List[int],
        staff_mapping: Dict[int, str],
        target_start: int,
        target_end: int
    ) -> List[Event]:
        """Extract time-ordered events from target measure range.
        
        Returns:
            List of Event objects with onset times relative to passage start
        """
        events = []
        in_target = False
        current_measure = 0
        current_time = 0.0  # Track absolute time in quarter notes
        passage_start_time = None  # Will be set when we enter target measures
        
        for line in lines:
            line = line.strip()
            
            # Track measure boundaries
            if line.startswith('='):
                measure_marker = line.split('\t')[0]
                if measure_marker.startswith('='):
                    try:
                        num_str = measure_marker[1:].rstrip('-').split()[0]
                        if num_str and num_str.isdigit():
                            new_measure = int(num_str)
                            if new_measure == target_start:
                                in_target = True
                                passage_start_time = current_time
                            elif new_measure > target_end:
                                break
                            current_measure = new_measure
                    except (ValueError, IndexError):
                        pass
                continue
            
            # Skip non-data lines
            if line.startswith('!'):
                continue
            
            # Track spine manipulations (affects staff_mapping)
            if line.startswith('*'):
                staff_mapping = self._update_staff_mapping(line, staff_mapping)
                continue
            
            # If not in target range, still track time for correct onset calculation
            if not in_target:
                # Advance time based on any note durations in this line
                tokens = line.split('\t')
                if tokens and self._is_note_token(tokens[0]):
                    duration = self._extract_duration(tokens[0])
                    if duration is not None:
                        current_time += duration
                continue
            
            # Parse data line and extract notes
            tokens = line.split('\t')
            if len(tokens) < 2:
                continue
            
            # Skip the last column (usually dynamics)
            note_tokens = tokens[:-1]
            
            # Extract notes from all columns at this time point
            line_duration = None  # Track duration to advance time
            
            for col_idx, token in enumerate(note_tokens):
                if not self._is_note_token(token):
                    continue
                
                # Extract pitch(es) - can be chord
                pitches = self._token_to_midi(token)
                if not pitches:
                    continue
                
                # Extract duration
                duration = self._extract_duration(token)
                if duration is None:
                    continue
                
                # Track line duration (use first note's duration)
                if line_duration is None:
                    line_duration = duration
                
                # Determine voice (staff1=RH, staff2=LH)
                staff = staff_mapping.get(col_idx, '*staff2')
                voice = 1 if 'staff1' in staff else 2
                
                # Check if grace note
                is_grace = self._is_grace_note(token)
                
                # Calculate onset relative to passage start
                if passage_start_time is not None:
                    onset = current_time - passage_start_time
                else:
                    onset = 0.0
                
                # Create events for all pitches in chord
                for pitch in pitches:
                    events.append(Event(
                        onset=onset,
                        pitch=pitch,
                        duration=duration,
                        voice=voice,
                        is_grace=is_grace
                    ))
            
            # Advance time by the duration of this line
            if line_duration is not None:
                current_time += line_duration
        
        return events
    
    def _update_staff_mapping(
        self,
        line: str,
        staff_mapping: Dict[int, str]
    ) -> Dict[int, str]:
        """Update staff mapping when spines split (*^) or join (*v)."""
        tokens = line.strip().split('\t')
        
        # Handle spine split (*^)
        if '*^' in tokens:
            new_mapping = {}
            col_out = 0
            for col_in, token in enumerate(tokens):
                if token == '*^':
                    # This spine splits into two
                    staff = staff_mapping.get(col_in, f'*staff{col_in}')
                    new_mapping[col_out] = staff
                    new_mapping[col_out + 1] = staff
                    col_out += 2
                else:
                    new_mapping[col_out] = staff_mapping.get(col_in, f'*staff{col_in}')
                    col_out += 1
            return new_mapping
        
        # Handle spine join (*v)
        elif '*v' in tokens:
            v_count = sum(1 for t in tokens if t == '*v')
            if v_count >= 2:
                new_mapping = {}
                col_out = 0
                skip_next = False
                for col_in, token in enumerate(tokens):
                    if skip_next:
                        skip_next = False
                        continue
                    if token == '*v' and col_in + 1 < len(tokens) and tokens[col_in + 1] == '*v':
                        # These two columns join into one
                        staff = staff_mapping.get(col_in, f'*staff{col_in}')
                        new_mapping[col_out] = staff
                        col_out += 1
                        skip_next = True
                    else:
                        new_mapping[col_out] = staff_mapping.get(col_in, f'*staff{col_in}')
                        col_out += 1
                return new_mapping
        
        return staff_mapping
    
    def _is_note_token(self, token: str) -> bool:
        """Check if token represents a note (not rest or null)."""
        token = token.strip()
        if not token or token.startswith('*') or token.startswith('!') or token.startswith('='):
            return False
        
        # Check for grace note (we'll extract them but mark them)
        # Grace notes have 'q' or 'qq' after pitch: 32bqLLL, 32ddqJJJ
        # We now extract grace notes but mark them with is_grace=True
        
        # Check for rest
        if 'r' in token.lower() and not any(c in token for c in 'abcdefgABCDEFG'):
            return False
        
        # Check for note (has pitch info)
        return any(c in token for c in 'abcdefgABCDEFG')
    
    def _is_grace_note(self, token: str) -> bool:
        """Check if token represents a grace note."""
        # Grace notes marked with 'q' or 'qq' after pitch
        return bool(re.search(r'[a-gA-G][#-]*P?qq?', token))
    
    def _token_to_midi(self, token: str) -> List[int]:
        """Convert Humdrum token to MIDI note number(s).
        
        Returns list because tokens can contain chords (space-separated).
        """
        pitches = []
        
        # Split by space to handle chords: "4CC 4C"
        for subtoken in token.split():
            pitch = self._parse_pitch(subtoken)
            if pitch is not None:
                pitches.append(pitch)
        
        return pitches
    
    def _parse_pitch(self, token: str) -> Optional[int]:
        """Parse a single Humdrum pitch token to MIDI number."""
        # Remove duration, articulation, ties, etc.
        token = token.strip()
        token = re.sub(r'\d+', '', token)  # Remove duration
        token = token.replace('[', '').replace(']', '').replace('_', '').replace('/', '')
        
        # Extract pitch class
        pitch_match = re.search(r'([a-gA-G])', token)
        if not pitch_match:
            return None
        
        pitch_letter = pitch_match.group(1)
        
        # Count sharps/flats
        sharps = token.count('#')
        flats = token.count('-')
        accidental = sharps - flats
        
        # Determine octave (lowercase = higher, uppercase = lower)
        if pitch_letter.islower():
            # c=C4, cc=C5, ccc=C6
            octave = 4 + (token.count(pitch_letter) - 1)
        else:
            # C=C3, CC=C2, CCC=C1
            octave = 3 - (token.count(pitch_letter) - 1)
        
        # Convert to MIDI
        pitch_classes = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
        pitch_class = pitch_classes[pitch_letter.lower()]
        midi = (octave + 1) * 12 + pitch_class + accidental
        
        return midi
    
    def _extract_duration(self, token: str) -> Optional[float]:
        """Extract duration from Humdrum token as quarter notes.
        
        Humdrum uses reciprocal notation:
        - 4 = quarter note = 1.0
        - 8 = eighth note = 0.5
        - 16 = 16th note = 0.25
        - 2 = half note = 2.0
        - 1 = whole note = 4.0
        """
        # Match duration number
        match = re.search(r'(\d+)', token)
        if not match:
            return None
        
        duration_num = int(match.group(1))
        # Convert reciprocal to quarter notes
        quarter_length = 4.0 / duration_num
        
        # Check for dot (adds 50% to duration)
        if '.' in token:
            quarter_length *= 1.5
        
        return quarter_length

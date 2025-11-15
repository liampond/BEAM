"""
Humdrum (**kern) format parser for automated answer generation.

Parses **kern encoded musical passages to extract information needed
for benchmark questions. Handles grace notes, ties, ornaments, spine
splits/merges, and multi-staff piano music across multiple measures.
"""

import re
from typing import List, Tuple, Optional, Set, Dict
from .base_parser import BaseParser, Note


class SpineTracker:
    """
    Tracks spine evolution through splits, merges, exchanges, and path changes.
    Essential for correctly identifying which notes belong to left/right hand.
    """
    
    def __init__(self, initial_spines: List[str]):
        """
        Initialize with spine interpretations (e.g., ['**kern', '**kern', '**dynam']).
        """
        self.spines = initial_spines.copy()
        self.kern_indices = [i for i, s in enumerate(initial_spines) if s == '**kern']
        
        # For piano music: typically staff2 (LH) comes first, then staff1 (RH)
        # But we'll track by explicit staff labels when available
        self.spine_to_staff: Dict[int, str] = {}
        self._assign_initial_staffs()
    
    def _assign_initial_staffs(self):
        """Assign initial staff mappings based on spine order."""
        if len(self.kern_indices) >= 2:
            # Standard piano: first kern = staff2 (LH), second kern = staff1 (RH)
            self.spine_to_staff[self.kern_indices[0]] = 'staff2'  # left hand
            self.spine_to_staff[self.kern_indices[1]] = 'staff1'  # right hand
    
    def update_staff_labels(self, tokens: List[str]):
        """Update staff assignments from *staff1/*staff2 interpretations."""
        for i, token in enumerate(tokens):
            if token == '*staff1':
                self.spine_to_staff[i] = 'staff1'
            elif token == '*staff2':
                self.spine_to_staff[i] = 'staff2'
    
    def process_spine_manipulation(self, tokens: List[str]):
        """
        Process spine path indicators:
        - *^ = split (one spine becomes two)
        - *v = merge (prepare for merge)
        - *x = exchange (swap adjacent spines)
        - *+ = add new spine
        - *- = terminate spine
        """
        if not any(t in ['*^', '*v', '*x', '*+', '*-'] for t in tokens):
            return
        
        # Handle splits first
        new_spines = []
        new_spine_to_staff = {}
        i = 0
        while i < len(self.spines):
            if i < len(tokens) and tokens[i] == '*^':
                # Split: one spine becomes two
                new_spines.append(self.spines[i])
                new_spines.append(self.spines[i])
                # Both new spines inherit the staff assignment
                staff = self.spine_to_staff.get(i)
                if staff:
                    new_spine_to_staff[len(new_spines) - 2] = staff
                    new_spine_to_staff[len(new_spines) - 1] = staff
            elif i < len(tokens) and tokens[i] == '*-':
                # Terminate: skip this spine
                pass
            else:
                new_spines.append(self.spines[i])
                staff = self.spine_to_staff.get(i)
                if staff:
                    new_spine_to_staff[len(new_spines) - 1] = staff
            i += 1
        
        # Handle merges (*v *v)
        if '*v' in tokens:
            merged_spines = []
            merged_staff = {}
            skip_next = False
            for i in range(len(new_spines)):
                if skip_next:
                    skip_next = False
                    continue
                if i < len(tokens) and tokens[i] == '*v' and i + 1 < len(tokens) and tokens[i + 1] == '*v':
                    # Merge two spines into one
                    merged_spines.append(new_spines[i])
                    staff = new_spine_to_staff.get(i)
                    if staff:
                        merged_staff[len(merged_spines) - 1] = staff
                    skip_next = True
                else:
                    merged_spines.append(new_spines[i])
                    staff = new_spine_to_staff.get(i)
                    if staff:
                        merged_staff[len(merged_spines) - 1] = staff
            new_spines = merged_spines
            new_spine_to_staff = merged_staff
        
        self.spines = new_spines
        self.spine_to_staff = new_spine_to_staff
        self.kern_indices = [i for i, s in enumerate(self.spines) if s == '**kern']
    
    def get_hand_for_spine(self, spine_idx: int) -> Optional[str]:
        """Get hand (left/right) for a spine index."""
        staff = self.spine_to_staff.get(spine_idx)
        if staff == 'staff1':
            return 'right'
        elif staff == 'staff2':
            return 'left'
        # Fallback to position-based assignment
        if spine_idx in self.kern_indices:
            pos = self.kern_indices.index(spine_idx)
            return 'left' if pos == 0 else 'right'
        return None


class HumdrumParser(BaseParser):
    """
    Robust parser for Humdrum **kern format.
    
    Handles:
    - Spine splits, merges, exchanges (*^, *v, *x)
    - Ties across barlines ([, _, ])
    - Grace notes (q suffix)
    - Chords (space-separated notes)
    - Ornaments (t/T for trills, etc.)
    - Multi-measure passages
    """
    
    def __init__(self):
        # Track active ties: key = (spine_idx, pitch), value = tie_id
        self.active_ties: Dict[Tuple[int, str], str] = {}
        self.tie_counter = 0
    
    def parse_passage(self, passage_text: str) -> Tuple[List[Note], List[Note]]:
        """
        Parse Humdrum passage into separate note lists for each hand.
        
        Properly handles:
        - Spine manipulations across the entire passage
        - Ties that cross barlines
        - Multiple measures
        - Grace notes and ornaments
        """
        lines = passage_text.strip().split('\n')
        
        left_notes = []
        right_notes = []
        current_beat = 0.0
        spine_tracker = None
        
        for line_num, line in enumerate(lines):
            line = line.rstrip()
            if not line:
                continue
            
            # Skip comments
            if line.startswith('!'):
                continue
            
            # Spine definitions - initialize tracker
            if line.startswith('**'):
                tokens = line.split('\t')
                spine_tracker = SpineTracker(tokens)
                continue
            
            if spine_tracker is None:
                continue
            
            # Interpretations
            if line.startswith('*'):
                tokens = line.split('\t')
                # Update staff labels
                spine_tracker.update_staff_labels(tokens)
                # Handle spine manipulations
                spine_tracker.process_spine_manipulation(tokens)
                continue
            
            # Measure marker - reset beat counter
            if line.startswith('='):
                current_beat = 0.0
                continue
            
            # Data line - parse notes
            tokens = line.split('\t')
            
            # Get duration from first kern spine to advance beat
            reference_duration = 0.0
            for idx in spine_tracker.kern_indices:
                if idx < len(tokens):
                    token = tokens[idx]
                    if token and token != '.':
                        reference_duration = self._extract_duration(token)
                        break
            
            # Parse all kern spines
            for spine_idx in spine_tracker.kern_indices:
                if spine_idx >= len(tokens):
                    continue
                
                token = tokens[spine_idx].strip()
                if not token or token == '.':
                    # Null token - means "same as previous"
                    continue
                
                # Skip invisible/null rests (ryy, Ryy, etc.)
                if 'ryy' in token.lower():
                    continue
                
                hand = spine_tracker.get_hand_for_spine(spine_idx)
                if not hand:
                    continue
                
                # Parse all notes/rests in this token
                notes = self._parse_token(token, hand, current_beat, spine_idx)
                
                if hand == 'left':
                    left_notes.extend(notes)
                else:
                    right_notes.extend(notes)
            
            # Advance beat
            current_beat += reference_duration
        
        return left_notes, right_notes
    
    def _parse_token(self, token: str, hand: str, beat_position: float, spine_idx: int) -> List[Note]:
        """
        Parse a single Humdrum token (can contain chords).
        
        Handles:
        - Chords (space-separated notes)
        - Grace notes (q/Q suffix)
        - Ties ([, _, ])
        - Rests (r)
        - Ornaments (t/T, etc.)
        """
        notes = []
        
        # Split chord notes (space-separated)
        note_strings = token.split()
        
        for note_str in note_strings:
            # Check if rest
            if 'r' in note_str:
                duration = self._extract_duration(note_str)
                notes.append(Note(
                    pitch='',
                    octave=0,
                    duration=duration,
                    duration_text=self.duration_to_text(duration),
                    hand=hand,
                    position=beat_position,
                    is_rest=True
                ))
                continue
            
            # Check if grace note
            is_grace = 'q' in note_str or 'Q' in note_str
            
            # Extract pitch
            pitch = self._extract_pitch(note_str)
            if not pitch:
                continue
            
            # Extract duration
            duration = self._extract_duration(note_str)
            
            # Handle ties
            is_tied_start = '[' in note_str
            is_tied_cont = '_' in note_str or ']' in note_str
            
            # Create tie key
            tie_key = (spine_idx, pitch)
            
            # Check if this note is a tied continuation
            is_tied_continuation = tie_key in self.active_ties
            
            # Update tie tracking
            if is_tied_start:
                # Start new tie
                self.tie_counter += 1
                self.active_ties[tie_key] = f"tie_{self.tie_counter}"
            elif ']' in note_str:
                # End tie
                if tie_key in self.active_ties:
                    del self.active_ties[tie_key]
            # '_' continues existing tie (no change needed)
            
            notes.append(Note(
                pitch=pitch,
                octave=int(pitch[-1]) if pitch[-1].isdigit() else 0,
                duration=duration,
                duration_text=self.duration_to_text(duration),
                hand=hand,
                position=beat_position,
                is_grace=is_grace,
                is_tied_continuation=is_tied_continuation
            ))
        
        return notes
    
    def _extract_pitch(self, token: str) -> Optional[str]:
        """
        Extract pitch from Humdrum token.
        
        Humdrum uses:
        - Lowercase letters = octave 4 and above (c=C4, cc=C5, ccc=C6)
        - Uppercase letters = octave 3 and below (C=C3, CC=C2, CCC=C1)
        - Accidentals: # for sharp, - for flat
        """
        # Remove duration numbers, grace note markers, ties, ornaments
        clean = re.sub(r'\d+', '', token)
        clean = re.sub(r'[qQ\[\]_]', '', clean)
        clean = re.sub(r'[Tt]', '', clean)  # Remove trills
        
        # Find pitch letter (case matters!)
        pitch_match = re.search(r'([a-gA-G]+)', clean)
        if not pitch_match:
            return None
        
        pitch_str = pitch_match.group(1)
        base_letter = pitch_str[0].upper()
        
        # Count repetitions to determine octave
        count = len(pitch_str)
        
        if pitch_str[0].islower():
            # Lowercase: c=C4, cc=C5, ccc=C6
            octave = 3 + count
        else:
            # Uppercase: C=C3, CC=C2, CCC=C1
            octave = 4 - count
        
        # Check for accidentals
        accidental = ''
        if '#' in clean:
            accidental = '#'
        elif '-' in clean:
            accidental = 'b'
        
        return f"{base_letter}{accidental}{octave}"
    
    def _extract_duration(self, token: str) -> float:
        """
        Extract duration from Humdrum token.
        
        Returns duration in quarter notes:
        - 1 = whole note (4 quarters)
        - 2 = half note (2 quarters)
        - 4 = quarter note (1 quarter)
        - 8 = eighth note (0.5 quarters)
        - 16 = sixteenth note (0.25 quarters)
        
        Dots multiply by 1.5
        """
        # Extract duration number
        duration_match = re.search(r'(\d+)', token)
        if not duration_match:
            return 0.0
        
        duration_num = int(duration_match.group(1))
        
        # Convert to quarter notes
        quarters = 4.0 / duration_num
        
        # Check for dots
        dot_count = token.count('.')
        if dot_count > 0:
            quarters *= (2.0 - 0.5 ** dot_count)
        
        return quarters
    
    # Implement BaseParser abstract methods
    
    def count_notes(
        self, 
        passage_text: str, 
        hand: Optional[str] = None,
        include_grace: bool = True,
        count_tied_once: bool = True
    ) -> int:
        """Count notes in passage."""
        left_notes, right_notes = self.parse_passage(passage_text)
        
        if hand == 'left':
            notes = left_notes
        elif hand == 'right':
            notes = right_notes
        else:
            notes = left_notes + right_notes
        
        # Filter based on criteria
        filtered = [n for n in notes if not n.is_rest]
        
        if not include_grace:
            filtered = [n for n in filtered if not n.is_grace]
        
        if count_tied_once:
            filtered = [n for n in filtered if not n.is_tied_continuation]
        
        return len(filtered)
    
    def count_rests(self, passage_text: str) -> int:
        """Count rests in passage."""
        left_notes, right_notes = self.parse_passage(passage_text)
        all_notes = left_notes + right_notes
        return sum(1 for n in all_notes if n.is_rest)
    
    def count_pitch_classes(self, passage_text: str, hand: str) -> int:
        """Count unique pitch classes (atonal sense)."""
        left_notes, right_notes = self.parse_passage(passage_text)
        notes = left_notes if hand == 'left' else right_notes
        
        # Extract pitch classes (remove octave)
        pitch_classes: Set[str] = set()
        for note in notes:
            if not note.is_rest and not note.is_tied_continuation:
                # Remove octave digit from pitch
                pitch_class = re.sub(r'\d+', '', note.pitch)
                pitch_classes.add(pitch_class)
        
        return len(pitch_classes)
    
    def get_first_pitch(
        self, 
        passage_text: str, 
        hand: str,
        include_octave: bool = True
    ) -> str:
        """Get first pitch in specified hand (highest if simultaneous)."""
        left_notes, right_notes = self.parse_passage(passage_text)
        notes = left_notes if hand == 'left' else right_notes
        
        # Filter out rests and get non-grace notes first
        real_notes = [n for n in notes if not n.is_rest and not n.is_tied_continuation]
        if not real_notes:
            return ""
        
        # Find first position
        first_pos = min(n.position for n in real_notes)
        first_notes = [n for n in real_notes if n.position == first_pos]
        
        # Choose highest if multiple simultaneous
        highest = max(first_notes, key=lambda n: self.pitch_to_semitones(n.pitch))
        
        if include_octave:
            return highest.pitch
        else:
            return re.sub(r'\d+', '', highest.pitch)
    
    def get_lowest_pitch(
        self, 
        passage_text: str, 
        hand: str,
        include_octave: bool = True
    ) -> str:
        """Get lowest pitch in specified hand."""
        left_notes, right_notes = self.parse_passage(passage_text)
        notes = left_notes if hand == 'left' else right_notes
        
        real_notes = [n for n in notes if not n.is_rest and not n.is_tied_continuation]
        if not real_notes:
            return ""
        
        lowest = min(real_notes, key=lambda n: self.pitch_to_semitones(n.pitch))
        
        if include_octave:
            return lowest.pitch
        else:
            return re.sub(r'\d+', '', lowest.pitch)
    
    def get_highest_pitch(
        self, 
        passage_text: str, 
        hand: str,
        include_octave: bool = True
    ) -> str:
        """Get highest pitch in specified hand."""
        left_notes, right_notes = self.parse_passage(passage_text)
        notes = left_notes if hand == 'left' else right_notes
        
        real_notes = [n for n in notes if not n.is_rest and not n.is_tied_continuation]
        if not real_notes:
            return ""
        
        highest = max(real_notes, key=lambda n: self.pitch_to_semitones(n.pitch))
        
        if include_octave:
            return highest.pitch
        else:
            return re.sub(r'\d+', '', highest.pitch)
    
    def get_first_note_duration(
        self, 
        passage_text: str, 
        hand: str,
        as_text: bool = True
    ) -> str:
        """Get duration of first note (highest if simultaneous)."""
        left_notes, right_notes = self.parse_passage(passage_text)
        notes = left_notes if hand == 'left' else right_notes
        
        real_notes = [n for n in notes if not n.is_rest and not n.is_tied_continuation]
        if not real_notes:
            return ""
        
        first_pos = min(n.position for n in real_notes)
        first_notes = [n for n in real_notes if n.position == first_pos]
        
        # Choose highest if multiple
        highest = max(first_notes, key=lambda n: self.pitch_to_semitones(n.pitch))
        
        if as_text:
            return highest.duration_text
        else:
            return str(highest.duration)
    
    def get_longest_note_duration(self, passage_text: str, as_text: bool = False) -> str:
        """Get duration of longest note in passage."""
        left_notes, right_notes = self.parse_passage(passage_text)
        all_notes = left_notes + right_notes
        
        real_notes = [n for n in all_notes if not n.is_rest and not n.is_tied_continuation]
        if not real_notes:
            return ""
        
        longest = max(real_notes, key=lambda n: n.duration)
        
        if as_text:
            return longest.duration_text
        else:
            # Return int if whole number, otherwise float
            if longest.duration == int(longest.duration):
                return str(int(longest.duration))
            return str(longest.duration)
    
    def calculate_interval(self, passage_text: str, hand: str) -> int:
        """Calculate interval in semitones between first and last notes."""
        left_notes, right_notes = self.parse_passage(passage_text)
        notes = left_notes if hand == 'left' else right_notes
        
        real_notes = [n for n in notes if not n.is_rest and not n.is_tied_continuation]
        if len(real_notes) < 2:
            return 0
        
        first_note = real_notes[0]
        last_note = real_notes[-1]
        
        first_semitones = self.pitch_to_semitones(first_note.pitch)
        last_semitones = self.pitch_to_semitones(last_note.pitch)
        
        return abs(last_semitones - first_semitones)
    
    def get_beat_position(
        self, 
        passage_text: str, 
        pitch: str, 
        hand: str
    ) -> Optional[float]:
        """Find on which beat a specific pitch first appears."""
        left_notes, right_notes = self.parse_passage(passage_text)
        notes = left_notes if hand == 'left' else right_notes
        
        for note in notes:
            if not note.is_rest and note.pitch == pitch:
                # Return 1-indexed beat position
                return note.position + 1.0
        
        return None
    
    def count_note_type(
        self, 
        passage_text: str, 
        note_type: str,
        hand: Optional[str] = None
    ) -> int:
        """Count specific note types."""
        left_notes, right_notes = self.parse_passage(passage_text)
        
        if hand == 'left':
            notes = left_notes
        elif hand == 'right':
            notes = right_notes
        else:
            notes = left_notes + right_notes
        
        # Map note type to duration
        type_duration_map = {
            'whole': 4.0,
            'half': 2.0,
            'quarter': 1.0,
            'eighth': 0.5,
            'sixteenth': 0.25,
            'thirty-second': 0.125,
        }
        
        target_duration = type_duration_map.get(note_type.lower())
        if target_duration is None:
            return 0
        
        return sum(1 for n in notes 
                  if not n.is_rest 
                  and not n.is_tied_continuation
                  and abs(n.duration - target_duration) < 0.01)

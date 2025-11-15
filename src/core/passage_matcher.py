#!/usr/bin/env python3
"""
Match passages across different music encoding formats by comparing musical content.

This module finds corresponding measures in ABC, MusicXML, and MEI files
by matching them against a reference Humdrum passage. It uses fuzzy matching
based on pitch sequences and intervallic relationships to handle encoding
differences like key signature representation and measure numbering.

Usage:
    from src.core.passage_matcher import find_passage_in_all_formats
    
    results = find_passage_in_all_formats(
        humdrum_file=Path('data/humdrum/01-1.krn'),
        abc_file=Path('data/abc/01-1.abc'),
        musicxml_file=Path('data/musicxml/01-1.xml'),
        mei_file=Path('data/mei/01-1.mei'),
        humdrum_start=87,
        humdrum_end=87
    )
    # Returns: {'humdrum': (87, 87), 'abc': (87, 87), ...}
"""

from pathlib import Path
from typing import Tuple, Optional, List
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass
class MatchingConfig:
    """Configuration for passage matching algorithm."""
    
    # Search window: how many measures before/after to search
    search_window: int = 10
    
    # Matching tolerances
    note_count_tolerance: int = 3  # Allow ±3 notes difference
    interval_tolerance: int = 1    # Allow ±1 semitone per interval
    chord_count_tolerance: int = 2  # Allow ±2 chord difference
    
    # Minimum requirements for interval matching
    min_notes_for_interval_match: int = 8
    min_matching_intervals: int = 2  # Out of first 3


class PassageMatcher:
    """
    Matches musical passages across different encoding formats.
    
    Uses Humdrum as the reference format and finds corresponding measures
    in ABC, MusicXML, and MEI by comparing musical signatures (pitches,
    intervals, rhythms).
    """
    
    def __init__(
        self, 
        humdrum_file: Path, 
        start_measure: int, 
        end_measure: int,
        config: Optional[MatchingConfig] = None
    ):
        """
        Initialize with a reference Humdrum passage.
        
        Args:
            humdrum_file: Path to Humdrum (.krn) file
            start_measure: Start measure number (1-indexed)
            end_measure: End measure number (inclusive)
            config: Optional configuration for matching algorithm
        """
        self.humdrum_file = humdrum_file
        self.start_measure = start_measure
        self.end_measure = end_measure
        self.config = config or MatchingConfig()
        self.reference_signature = self._extract_humdrum_signature()
    
    def _extract_humdrum_signature(self) -> dict:
        """
        Extract a musical signature from the Humdrum passage.
        
        Returns a dict with:
        - pitch_sequence: List of pitches in order (MIDI note numbers)
        - rhythm_pattern: List of duration ratios
        - chord_count: Number of simultaneous notes
        - measure_count: Number of measures
        """
        with open(self.humdrum_file, 'r') as f:
            lines = f.readlines()
        
        # Find measure offset
        offset = self._get_humdrum_measure_offset(lines)
        target_start = self.start_measure + offset - 1
        target_end = self.end_measure + offset - 1
        
        # Extract notes from target measures
        rh_pitches = []
        lh_pitches = []
        rhythms = []
        chord_count = 0
        in_target = False
        current_measure = 0
        
        for line in lines:
            line = line.strip()
            
            # Track measure numbers
            if line.startswith('='):
                measure_marker = line.split('\t')[0]
                if measure_marker.startswith('='):
                    try:
                        num_str = measure_marker[1:].rstrip('-').split()[0]
                        if num_str and num_str.isdigit():
                            current_measure = int(num_str)
                            if current_measure == target_start:
                                in_target = True
                            elif current_measure > target_end:
                                break
                    except (ValueError, IndexError):
                        pass
                continue
            
            # Skip non-data lines
            if not in_target or line.startswith('*') or line.startswith('!'):
                continue
            
            # Parse data tokens - column 0 is LH, column 1 is RH
            tokens = line.split('\t')
            if len(tokens) < 2:
                continue
            
            lh_token = tokens[0] if len(tokens) > 0 else ''
            rh_token = tokens[1] if len(tokens) > 1 else ''
            
            # Count chords (multiple simultaneous pitches in either hand)
            lh_pitches_in_token = self._humdrum_to_midi(lh_token) if self._is_note_token(lh_token) else []
            rh_pitches_in_token = self._humdrum_to_midi(rh_token) if self._is_note_token(rh_token) else []
            
            if len(lh_pitches_in_token) > 1:
                chord_count += 1
            if len(rh_pitches_in_token) > 1:
                chord_count += 1
            
            # Extract RH pitch(es)
            if self._is_note_token(rh_token):
                pitches_in_token = rh_pitches_in_token
                rh_pitches.extend(pitches_in_token)
                duration = self._extract_duration(rh_token)
                if duration is not None:
                    rhythms.append(duration)
            
            # Extract LH pitch(es)
            if self._is_note_token(lh_token):
                pitches_in_token = lh_pitches_in_token
                lh_pitches.extend(pitches_in_token)
                duration = self._extract_duration(lh_token)
                if duration is not None:
                    rhythms.append(duration)
        
        # Combine RH first, then LH for consistent ordering
        pitches = rh_pitches + lh_pitches
        
        return {
            'pitches': pitches,
            'rhythms': rhythms,
            'chord_count': chord_count,
            'measure_count': self.end_measure - self.start_measure + 1,
            'first_pitches': pitches[:10] if pitches else [],  # First 10 pitches for quick matching
            'last_pitches': pitches[-5:] if pitches else [],   # Last 5 pitches
            'total_notes': len(pitches),
            'rh_count': len(rh_pitches),
            'lh_count': len(lh_pitches)
        }
    
    def _get_humdrum_measure_offset(self, lines: List[str]) -> int:
        """Get the measure number offset for Humdrum file."""
        for line in lines:
            if not line.startswith('='):
                continue
            token = line.split('\t', 1)[0][1:].rstrip('-').split()[0]
            if token and token.isdigit():
                value = int(token)
                return value if value != 0 else 0
        return 1
    
    def _is_note_token(self, token: str) -> bool:
        """Check if Humdrum token represents a note (not rest or null)."""
        token = token.strip()
        if not token or token.startswith('*') or token.startswith('!') or token.startswith('='):
            return False
        # Check for grace notes (marked with 'q' or 'qq' after the pitch in Humdrum)
        # Grace notes have markers like: 32bqLLL, 32ddqJJJ, 32g#Pqq/, 32bPqq/
        # The 'q' appears after the pitch letter (and accidentals) and before or with other markers
        # Pattern: pitch letter + optional accidentals + optional 'P' + 'q' or 'qq'
        if re.search(r'[a-gA-G][#-]*P?qq?', token):
            return False
        # Check for rest
        if 'r' in token.lower() and not any(c in token for c in 'abcdefgABCDEFG'):
            return False
        # Check for note (has pitch info)
        return any(c in token for c in 'abcdefgABCDEFG')
    
    def _humdrum_to_midi(self, token: str) -> list:
        """
        Convert Humdrum pitch token to MIDI note number(s).
        Returns a list because tokens can contain chords (space-separated pitches).
        """
        # Handle chords: tokens like "4CC 4C" have multiple pitches separated by space
        pitches = []
        
        # Split by space to handle chords
        for subtoken in token.split():
            pitch = self._parse_single_humdrum_pitch(subtoken)
            if pitch is not None:
                pitches.append(pitch)
        
        return pitches
    
    def _parse_single_humdrum_pitch(self, token: str) -> Optional[int]:
        """Parse a single Humdrum pitch (not a chord)."""
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
            # Count lowercase letters for octave
            octave = 4 + token.count(pitch_letter)
        else:
            # Count uppercase letters for octave (inverted)
            octave = 3 - token.count(pitch_letter)
        
        # Convert to MIDI
        pitch_classes = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
        pitch_class = pitch_classes[pitch_letter.lower()]
        midi = (octave + 1) * 12 + pitch_class + accidental
        
        return midi
    
    def _extract_duration(self, token: str) -> Optional[float]:
        """Extract duration from Humdrum token as a float."""
        # Match duration number
        match = re.search(r'(\d+)', token)
        if not match:
            return None
        
        duration = int(match.group(1))
        # Check for dot
        if '.' in token:
            return duration * 1.5
        return float(duration)
    
    def find_in_abc(self, abc_file: Path) -> Optional[Tuple[int, int]]:
        """
        Find matching measures in ABC file.
        
        Searches around the Humdrum measure number ±10 measures to account
        for different repeat structures and measure numbering.
        
        Returns:
            (start_measure, end_measure) or None if not found
        """
        with open(abc_file, 'r') as f:
            content = f.read()
        
        # Split into header and body
        lines = content.split('\n')
        body_start = 0
        for i, line in enumerate(lines):
            if line.startswith('K:'):
                body_start = i + 1
                break
        
        body_lines = lines[body_start:]
        
        # Extract all measures with their content
        measures = []
        current_measure = {'v1': '', 'v2': '', 'number': 0}
        measure_number = 0
        
        for line in body_lines:
            if line.startswith('[V:1]'):
                if '|' in line:
                    measure_number += 1
                    if current_measure['v1']:  # Save previous measure
                        measures.append(current_measure)
                    current_measure = {'v1': line, 'v2': '', 'number': measure_number}
                else:
                    current_measure['v1'] += ' ' + line
            elif line.startswith('[V:2]'):
                current_measure['v2'] += ' ' + line
        
        # Don't forget last measure
        if current_measure['v1']:
            measures.append(current_measure)
        
        # Search around the Humdrum measure number (±10 measures)
        search_start = max(0, self.start_measure - self.config.search_window)
        search_end = min(len(measures), self.start_measure + self.config.search_window)
        
        target_note_count = self.reference_signature['total_notes']
        target_measure_count = self.reference_signature['measure_count']
        
        # Try all possible measure ranges within search window
        for start_idx in range(search_start, search_end):
            if start_idx >= len(measures):
                break
            for end_idx in range(start_idx, min(start_idx + target_measure_count + 1, len(measures))):
                # Extract signature from this range
                measure_range = measures[start_idx:end_idx + 1]
                signature = self._extract_abc_signature(measure_range)
                
                # Compare signatures
                if self._signatures_match(signature, self.reference_signature):
                    return (measure_range[0]['number'], measure_range[-1]['number'])
        
        return None
    
    def _extract_abc_signature(self, measures: List[dict]) -> dict:
        """Extract musical signature from ABC measures."""
        pitches = []
        rhythms = []
        chord_count = 0
        
        for measure in measures:
            # Process V:1 (RH) and V:2 (LH) separately to match Humdrum order
            v1_content = measure['v1']
            v2_content = measure['v2']
            
            # Remove grace notes (in braces {}) before processing
            v1_content = re.sub(r'\{[^}]*\}', '', v1_content)
            v2_content = re.sub(r'\{[^}]*\}', '', v2_content)
            
            # Remove voice markers [V:1], [V:2], etc.
            v1_content = re.sub(r'\[V:\d+\]', '', v1_content)
            v2_content = re.sub(r'\[V:\d+\]', '', v2_content)
            
            # Process V:1 (RH) first, then V:2 (LH) to match Humdrum order
            for content in [v1_content, v2_content]:
                # Find chords and individual notes in order
                # We need to extract them in the order they appear, not chords-then-notes
                
                # Find all note-like patterns (both in chords and individual)
                # Process chords
                chord_matches = re.findall(r'\[([^\]]+)\]', content)
                for chord_content in chord_matches:
                    # Parse notes in chord
                    notes = re.findall(r'([_=\^]?)([A-Ga-g][,\']*)(\d*)', chord_content)
                    note_count_in_chord = 0
                    for accidental, pitch, duration in notes:
                        if pitch and pitch not in 'zZxX':
                            midi = self._abc_to_midi(accidental + pitch)
                            if midi is not None:
                                pitches.append(midi)
                                note_count_in_chord += 1
                    # Only count as chord if 2+ notes
                    if note_count_in_chord >= 2:
                        chord_count += 1
                
                # Find individual notes (not in chords, not rests)
                # Remove chords first
                no_chords = re.sub(r'\[[^\]]+\]', '', content)
                # Find notes
                note_matches = re.findall(r'([_=\^]?)([A-Ga-g][,\']*)(\d*)', no_chords)
                for accidental, pitch, duration in note_matches:
                    if pitch and pitch not in 'zZxX':
                        midi = self._abc_to_midi(accidental + pitch)
                        if midi is not None:
                            pitches.append(midi)
        
        return {
            'pitches': pitches,
            'chord_count': chord_count,
            'first_pitches': pitches[:10] if pitches else [],
            'last_pitches': pitches[-5:] if pitches else [],
            'total_notes': len(pitches)
        }
    
    def _abc_to_midi(self, note: str) -> Optional[int]:
        """Convert ABC note to MIDI number."""
        # Parse accidental
        accidental = 0
        if note.startswith('_'):
            accidental = -1
            note = note[1:]
        elif note.startswith('^'):
            accidental = 1
            note = note[1:]
        elif note.startswith('='):
            accidental = 0
            note = note[1:]
        
        # Parse pitch letter
        if not note:
            return None
        
        pitch_letter = note[0]
        rest = note[1:]
        
        # Determine octave
        # In ABC notation:
        # C, D, E ... = octave 2
        # C D E ... (uppercase) = octave 3
        # c d e ... (lowercase) = octave 4 (middle C octave)
        # c' d' e' ... = octave 5
        # c'' d'' e'' ... = octave 6
        # Each ' raises octave, each , lowers it
        if pitch_letter.isupper():
            octave = 3
        else:
            octave = 4
        
        octave += rest.count("'")
        octave -= rest.count(',')
        
        # Convert to MIDI
        pitch_classes = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
        pitch_class = pitch_classes[pitch_letter.lower()]
        midi = (octave + 1) * 12 + pitch_class + accidental
        
        return midi
    
    def _signatures_match(self, sig1: dict, sig2: dict) -> bool:
        """
        Compare two musical signatures to determine if they match.
        
        Uses fuzzy matching to account for encoding differences, key signature issues.
        Tolerances are configurable via MatchingConfig.
        
        Args:
            sig1: First signature dictionary
            sig2: Second signature dictionary
            
        Returns:
            True if signatures match within tolerances
        """
        # Check note count (configurable tolerance)
        note_diff = abs(sig1['total_notes'] - sig2['total_notes'])
        
        # Try interval-based matching first (more robust to encoding differences)
        # This works even when note counts differ significantly
        if sig1['total_notes'] >= self.config.min_notes_for_interval_match and \
           sig2['total_notes'] >= self.config.min_notes_for_interval_match:
            if len(sig1['first_pitches']) >= 3 and len(sig2['first_pitches']) >= 3:
                # Compare intervals between consecutive notes
                intervals1 = [sig1['first_pitches'][i+1] - sig1['first_pitches'][i] 
                             for i in range(min(4, len(sig1['first_pitches'])-1))]
                intervals2 = [sig2['first_pitches'][i+1] - sig2['first_pitches'][i] 
                             for i in range(min(4, len(sig2['first_pitches'])-1))]
                
                # Allow configurable semitone difference per interval
                if len(intervals1) >= 3 and len(intervals2) >= 3:
                    matching_intervals = sum(
                        1 for i1, i2 in zip(intervals1[:3], intervals2[:3]) 
                        if abs(i1 - i2) <= self.config.interval_tolerance
                    )
                    # If intervals match well, accept even if note counts differ
                    if matching_intervals >= self.config.min_matching_intervals:
                        # But note counts should be somewhat close
                        if note_diff <= self.config.note_count_tolerance * 3:
                            return True
        
        # If note count differs too much, reject
        if note_diff > self.config.note_count_tolerance:
            return False
        
        # Original strict matching for cases where intervals don't work
        # Check first pitches (must match exactly for first 5)
        if len(sig1['first_pitches']) < 5 or len(sig2['first_pitches']) < 5:
            return False
        
        first_match = sig1['first_pitches'][:5] == sig2['first_pitches'][:5]
        if not first_match:
            return False
        
        # Check last pitches (should match if not too different)
        if len(sig1['last_pitches']) >= 3 and len(sig2['last_pitches']) >= 3:
            last_match = sig1['last_pitches'][-3:] == sig2['last_pitches'][-3:]
            if not last_match:
                return False
        
        # Check chord count (configurable tolerance)
        chord_diff = abs(sig1.get('chord_count', 0) - sig2.get('chord_count', 0))
        if chord_diff > self.config.chord_count_tolerance:
            return False
        
        return True
    
    def find_in_musicxml(self, xml_file: Path) -> Optional[Tuple[int, int]]:
        """
        Find matching measures in MusicXML file.
        
        Searches around the Humdrum measure number ±10 measures.
        
        Returns:
            (start_measure, end_measure) or None if not found
        """
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
        except ET.ParseError:
            return None
        
        # Find all measures
        measures = root.findall('.//{http://www.musicxml.org/ns1.1}measure') or root.findall('.//measure')
        
        # Search around the Humdrum measure number (±10 measures)
        search_start = max(0, self.start_measure - self.config.search_window)
        search_end = min(len(measures), self.start_measure + self.config.search_window)
        target_measure_count = self.reference_signature['measure_count']
        
        for start_idx in range(search_start, search_end):
            if start_idx >= len(measures):
                break
            for end_idx in range(start_idx, min(start_idx + target_measure_count + 1, len(measures))):
                measure_range = measures[start_idx:end_idx + 1]
                signature = self._extract_musicxml_signature(measure_range)
                
                if self._signatures_match(signature, self.reference_signature):
                    # Get measure numbers
                    start_num = int(measure_range[0].get('number', '0'))
                    end_num = int(measure_range[-1].get('number', '0'))
                    return (start_num, end_num)
        
        return None
    
    def _extract_musicxml_signature(self, measures: List[ET.Element]) -> dict:
        """Extract musical signature from MusicXML measures."""
        pitches = []
        chord_count = 0
        
        for measure in measures:
            # Find all notes
            notes = measure.findall('.//{http://www.musicxml.org/ns1.1}note') or measure.findall('.//note')
            
            in_chord = False
            for note in notes:
                # Check if it's a grace note - skip if it is
                grace_elem = note.find('.//{http://www.musicxml.org/ns1.1}grace') or note.find('.//grace')
                if grace_elem is not None:
                    continue
                
                # Check if it's a chord
                chord_elem = note.find('.//{http://www.musicxml.org/ns1.1}chord') or note.find('.//chord')
                if chord_elem is not None:
                    if not in_chord:
                        chord_count += 1
                        in_chord = True
                else:
                    in_chord = False
                
                # Check if it's a rest
                rest_elem = note.find('.//{http://www.musicxml.org/ns1.1}rest') or note.find('.//rest')
                if rest_elem is not None:
                    continue
                
                # Extract pitch
                pitch_elem = note.find('.//{http://www.musicxml.org/ns1.1}pitch') or note.find('.//pitch')
                if pitch_elem is not None:
                    step_elem = pitch_elem.find('.//{http://www.musicxml.org/ns1.1}step') or pitch_elem.find('.//step')
                    octave_elem = pitch_elem.find('.//{http://www.musicxml.org/ns1.1}octave') or pitch_elem.find('.//octave')
                    alter_elem = pitch_elem.find('.//{http://www.musicxml.org/ns1.1}alter') or pitch_elem.find('.//alter')
                    
                    if step_elem is not None and octave_elem is not None and step_elem.text and octave_elem.text:
                        step = step_elem.text
                        octave = int(octave_elem.text)
                        alter = int(alter_elem.text) if alter_elem is not None and alter_elem.text else 0
                        
                        # Convert to MIDI
                        pitch_classes = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
                        midi = (octave + 1) * 12 + pitch_classes[step] + alter
                        pitches.append(midi)
        
        return {
            'pitches': pitches,
            'chord_count': chord_count,
            'first_pitches': pitches[:10] if pitches else [],
            'last_pitches': pitches[-5:] if pitches else [],
            'total_notes': len(pitches)
        }
    
    def find_in_mei(self, mei_file: Path) -> Optional[Tuple[int, int]]:
        """
        Find matching measures in MEI file.
        
        Searches around the Humdrum measure number ±10 measures.
        
        Returns:
            (start_measure, end_measure) or None if not found
        """
        try:
            tree = ET.parse(mei_file)
            root = tree.getroot()
        except ET.ParseError:
            return None
        
        ns = {'mei': 'http://www.music-encoding.org/ns/mei'}
        
        # Find all measures
        measures = root.findall('.//mei:measure', ns)
        
        # Search around the Humdrum measure number (±10 measures)
        search_start = max(0, self.start_measure - self.config.search_window)
        search_end = min(len(measures), self.start_measure + self.config.search_window)
        target_measure_count = self.reference_signature['measure_count']
        
        for start_idx in range(search_start, search_end):
            if start_idx >= len(measures):
                break
            for end_idx in range(start_idx, min(start_idx + target_measure_count + 1, len(measures))):
                measure_range = measures[start_idx:end_idx + 1]
                signature = self._extract_mei_signature(measure_range, ns)
                
                if self._signatures_match(signature, self.reference_signature):
                    # Get measure numbers
                    start_num = int(measure_range[0].get('n', '0'))
                    end_num = int(measure_range[-1].get('n', '0'))
                    return (start_num, end_num)
        
        return None
    
    def _extract_mei_signature(self, measures: List[ET.Element], ns: dict) -> dict:
        """Extract musical signature from MEI measures."""
        pitches = []
        chord_count = 0
        
        for measure in measures:
            # Find all notes
            notes = measure.findall('.//mei:note', ns)
            
            # Find chords
            chords = measure.findall('.//mei:chord', ns)
            chord_count += len(chords)
            
            for note in notes:
                # Check if it's a grace note - skip if it is
                grace_attr = note.get('grace')
                if grace_attr is not None:  # Grace notes have grace='unknown' or grace='acc' etc.
                    continue
                
                # Check if it's a rest (has no @pname)
                pname = note.get('pname')
                if not pname:
                    continue
                
                # Extract pitch
                octave = note.get('oct')
                accid = note.get('accid') or note.get('accid.ges')
                
                if octave:
                    # Convert to MIDI
                    pitch_classes = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
                    pitch_class = pitch_classes[pname.lower()]
                    
                    alter = 0
                    if accid == 's':
                        alter = 1
                    elif accid == 'f':
                        alter = -1
                    elif accid == 'ss':
                        alter = 2
                    elif accid == 'ff':
                        alter = -2
                    
                    midi = (int(octave) + 1) * 12 + pitch_class + alter
                    pitches.append(midi)
        
        return {
            'pitches': pitches,
            'chord_count': chord_count,
            'first_pitches': pitches[:10] if pitches else [],
            'last_pitches': pitches[-5:] if pitches else [],
            'total_notes': len(pitches)
        }


def find_passage_in_all_formats(
    humdrum_file: Path,
    abc_file: Path,
    musicxml_file: Path,
    mei_file: Path,
    humdrum_start: int,
    humdrum_end: int
) -> dict:
    """
    Find corresponding measures across all formats.
    
    Args:
        humdrum_file: Path to Humdrum file
        abc_file: Path to ABC file  
        musicxml_file: Path to MusicXML file
        mei_file: Path to MEI file
        humdrum_start: Start measure in Humdrum (1-indexed)
        humdrum_end: End measure in Humdrum (inclusive)
    
    Returns:
        Dict with format -> (start, end) measure numbers
    """
    matcher = PassageMatcher(humdrum_file, humdrum_start, humdrum_end)
    
    results = {
        'humdrum': (humdrum_start, humdrum_end)
    }
    
    if abc_file.exists():
        abc_measures = matcher.find_in_abc(abc_file)
        if abc_measures:
            results['abc'] = abc_measures
    
    if musicxml_file.exists():
        xml_measures = matcher.find_in_musicxml(musicxml_file)
        if xml_measures:
            results['musicxml'] = xml_measures
    
    if mei_file.exists():
        mei_measures = matcher.find_in_mei(mei_file)
        if mei_measures:
            results['mei'] = mei_measures
    
    return results

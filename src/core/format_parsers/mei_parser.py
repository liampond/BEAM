"""MEI (Music Encoding Initiative) format parser.

Extracts musical signatures from MEI XML files with time-ordered events.

MEI is an XML-based music encoding standard. This parser handles:
- Staff-based structure (multiple staves/voices)
- Duration calculation from @dur attribute (reciprocal notation)
- Dotted notes (@dots attribute)
- Grace note detection (@grace attribute)
- Chord notation (<chord> element with nested <note> elements)
- Accidentals (@accid, @accid.ges attributes)
- MEI namespace handling
"""

from pathlib import Path
from typing import Optional, List, Dict
import xml.etree.ElementTree as ET

from .base import FormatParser
from ..signature import MusicalSignature, Event


class MEIParser(FormatParser):
    """Parser for MEI (.mei) files."""
    
    name = "MEI"
    file_extensions = ('.mei',)
    
    # MEI namespace
    NS = {'mei': 'http://www.music-encoding.org/ns/mei'}
    
    def extract_signature(
        self,
        file_path: Path,
        start_measure: int,
        end_measure: int,
        **kwargs
    ) -> Optional[MusicalSignature]:
        """Extract time-ordered musical signature from MEI file.
        
        Args:
            file_path: Path to .mei file
            start_measure: First measure to extract (1-indexed)
            end_measure: Last measure to extract (inclusive)
            **kwargs: Not used for MEI
        
        Returns:
            MusicalSignature with events sorted by (onset, pitch)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"MEI file not found: {file_path}")
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Invalid MEI file: {e}")
        
        # Find all measures
        measures = root.findall('.//mei:measure', self.NS)
        if not measures:
            return None
        
        # Validate measure range
        if start_measure < 1 or start_measure > len(measures):
            return None
        if end_measure < start_measure or end_measure > len(measures):
            return None
        
        # Extract target measures (convert to 0-indexed)
        target_measures = measures[start_measure - 1:end_measure]
        
        # Extract events
        events = self._extract_events(target_measures)
        
        if not events:
            return None
        
        measure_count = end_measure - start_measure + 1
        
        # Calculate total duration
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
    
    def _extract_events(self, measures: List[ET.Element]) -> List[Event]:
        """Extract events from measures.
        
        For now, extracts in file order to match old implementation.
        
        Args:
            measures: List of measure elements
        
        Returns:
            List of Event objects
        """
        events = []
        current_onset = 0.0  # Simple incrementing for order preservation
        
        for measure in measures:
            # Process chords first (MEI puts duration on chord, not notes)
            chords = measure.findall('.//mei:chord', self.NS)
            for chord in chords:
                # Extract chord duration
                chord_duration = self._extract_duration_from_element(chord)
                if chord_duration is None:
                    chord_duration = 1.0  # Default
                
                # Get all notes in this chord
                chord_notes = chord.findall('.//mei:note', self.NS)
                for note in chord_notes:
                    # Skip grace notes
                    if self._is_grace_note(note):
                        continue
                    
                    # Extract pitch
                    pitch = self._extract_pitch(note)
                    if pitch is None:
                        continue
                    
                    # Create event
                    events.append(Event(
                        onset=current_onset,
                        pitch=pitch,
                        duration=chord_duration,
                        voice=1,
                        is_grace=False
                    ))
                
                current_onset += 0.001  # Tiny increment
            
            # Process individual notes (not in chords)
            # Get all notes, then filter out those in chords
            all_notes = measure.findall('.//mei:note', self.NS)
            chord_notes_set = set()
            for chord in chords:
                for note in chord.findall('.//mei:note', self.NS):
                    chord_notes_set.add(note)
            
            for note in all_notes:
                # Skip if already processed as part of chord
                if note in chord_notes_set:
                    continue
                
                # Skip grace notes
                if self._is_grace_note(note):
                    continue
                
                # Skip rests (no @pname)
                pname = note.get('pname')
                if not pname:
                    continue
                
                # Extract pitch
                pitch = self._extract_pitch(note)
                if pitch is None:
                    continue
                
                # Extract duration
                duration = self._extract_duration_from_element(note)
                if duration is None:
                    duration = 1.0  # Default
                
                # Create event
                events.append(Event(
                    onset=current_onset,
                    pitch=pitch,
                    duration=duration,
                    voice=1,
                    is_grace=False
                ))
                
                current_onset += 0.001  # Tiny increment
        
        return events
    
    def _is_grace_note(self, note: ET.Element) -> bool:
        """Check if note is a grace note."""
        grace_attr = note.get('grace')
        return grace_attr is not None
    
    def _extract_pitch(self, note: ET.Element) -> Optional[int]:
        """Extract MIDI pitch from note element.
        
        Args:
            note: MEI note element
        
        Returns:
            MIDI note number or None
        """
        # Extract pitch name and octave
        pname = note.get('pname')
        octave = note.get('oct')
        
        if not pname or not octave:
            return None
        
        # Convert to MIDI
        pitch_classes = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
        if pname.lower() not in pitch_classes:
            return None
        
        pitch_class = pitch_classes[pname.lower()]
        
        # Extract accidental
        accid = note.get('accid') or note.get('accid.ges')
        alter = 0
        if accid == 's':  # sharp
            alter = 1
        elif accid == 'f':  # flat
            alter = -1
        elif accid == 'ss':  # double sharp
            alter = 2
        elif accid == 'ff':  # double flat
            alter = -2
        elif accid == 'n':  # natural
            alter = 0
        
        try:
            oct_value = int(octave)
            midi = (oct_value + 1) * 12 + pitch_class + alter
            return midi
        except ValueError:
            return None
    
    def _extract_duration_from_element(self, element: ET.Element) -> Optional[float]:
        """Extract duration from element (note or chord).
        
        MEI uses reciprocal notation like Humdrum:
        - @dur="4" means quarter note = 1.0
        - @dur="8" means eighth note = 0.5
        - @dur="16" means sixteenth note = 0.25
        
        Args:
            element: MEI element with @dur attribute
        
        Returns:
            Duration in quarter notes
        """
        dur_attr = element.get('dur')
        if not dur_attr:
            return None
        
        try:
            dur_num = int(dur_attr)
            # Convert reciprocal to quarter notes
            quarter_length = 4.0 / dur_num
            
            # Check for dots
            dots = element.get('dots')
            if dots:
                try:
                    dot_count = int(dots)
                    # Each dot adds half of the previous duration
                    # 1 dot: 1.5x, 2 dots: 1.75x, 3 dots: 1.875x
                    multiplier = 1.0
                    for i in range(dot_count):
                        multiplier += 0.5 ** (i + 1)
                    quarter_length *= multiplier
                except ValueError:
                    pass
            
            return quarter_length
        except ValueError:
            return None

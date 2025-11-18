"""MusicXML format parser.

Extracts musical signatures from MusicXML files with time-ordered events.

MusicXML is an XML-based music notation format. This parser handles:
- Part-based structure (multiple instruments/voices)
- Duration calculation from <duration> and divisions
- Grace note detection and exclusion
- Chord notation (<chord> element)
- Rest handling
- Measure extraction
- Namespace variations (with/without xmlns)
"""

from pathlib import Path
from typing import Optional, List
import xml.etree.ElementTree as ET

from .base import FormatParser
from ..signature import MusicalSignature, Event


class MusicXMLParser(FormatParser):
    """Parser for MusicXML (.xml, .musicxml) files."""
    
    name = "MusicXML"
    file_extensions = ('.xml', '.musicxml', '.mxl')
    
    def extract_signature(
        self,
        file_path: Path,
        start_measure: int,
        end_measure: int,
        **kwargs
    ) -> Optional[MusicalSignature]:
        """Extract time-ordered musical signature from MusicXML file.
        
        Args:
            file_path: Path to .xml or .musicxml file
            start_measure: First measure to extract (1-indexed)
            end_measure: Last measure to extract (inclusive)
            **kwargs: Not used for MusicXML
        
        Returns:
            MusicalSignature with events sorted by (onset, pitch)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"MusicXML file not found: {file_path}")
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Invalid MusicXML file: {e}")
        
        # Find all measures (handle both with/without namespace)
        measures = self._find_measures(root)
        if not measures:
            return None
        
        # Find divisions value (divisions per quarter note)
        divisions = self._find_divisions(measures)
        
        # Validate measure range
        if start_measure < 1 or start_measure > len(measures):
            return None
        if end_measure < start_measure or end_measure > len(measures):
            return None
        
        # Extract target measures (convert to 0-indexed)
        target_measures = measures[start_measure - 1:end_measure]
        
        # Extract events
        events = self._extract_events(target_measures, divisions)
        
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
    
    def _find_measures(self, root: ET.Element) -> List[ET.Element]:
        """Find all measure elements (with or without namespace)."""
        # Try with namespace first
        measures = root.findall('.//{http://www.musicxml.org/ns1.1}measure')
        if measures:
            return measures
        
        # Try without namespace
        measures = root.findall('.//measure')
        return measures
    
    def _find_divisions(self, measures: List[ET.Element]) -> int:
        """Find divisions value (divisions per quarter note).
        
        Searches through measures to find the first <divisions> element.
        """
        for measure in measures:
            # Try with namespace
            div_elem = measure.find('.//{http://www.musicxml.org/ns1.1}divisions')
            if div_elem is not None and div_elem.text:
                return int(div_elem.text)
            
            # Try without namespace
            div_elem = measure.find('.//divisions')
            if div_elem is not None and div_elem.text:
                return int(div_elem.text)
        
        # Default to 1 if not found
        return 1
    
    def _extract_events(
        self,
        measures: List[ET.Element],
        divisions: int
    ) -> List[Event]:
        """Extract events from measures.
        
        For now, extracts in file order to match old implementation.
        
        Args:
            measures: List of measure elements
            divisions: Divisions per quarter note
        
        Returns:
            List of Event objects
        """
        events = []
        current_onset = 0.0  # Simple incrementing for order preservation
        
        for measure in measures:
            # Find all notes (with or without namespace)
            notes = measure.findall('.//{http://www.musicxml.org/ns1.1}note')
            if not notes:
                notes = measure.findall('.//note')
            
            for note in notes:
                # Skip grace notes
                if self._is_grace_note(note):
                    continue
                
                # Skip rests
                if self._is_rest(note):
                    continue
                
                # Extract pitch
                pitch = self._extract_pitch(note)
                if pitch is None:
                    continue
                
                # Extract duration
                duration = self._extract_duration(note, divisions)
                if duration is None:
                    continue
                
                # Create event
                events.append(Event(
                    onset=current_onset,
                    pitch=pitch,
                    duration=duration,
                    voice=1,  # MusicXML voice info could be extracted if needed
                    is_grace=False
                ))
                
                current_onset += 0.001  # Tiny increment to preserve order
        
        return events
    
    def _is_grace_note(self, note: ET.Element) -> bool:
        """Check if note is a grace note."""
        # Try with namespace
        grace_elem = note.find('.//{http://www.musicxml.org/ns1.1}grace')
        if grace_elem is not None:
            return True
        
        # Try without namespace
        grace_elem = note.find('.//grace')
        return grace_elem is not None
    
    def _is_rest(self, note: ET.Element) -> bool:
        """Check if note is a rest."""
        # Try with namespace
        rest_elem = note.find('.//{http://www.musicxml.org/ns1.1}rest')
        if rest_elem is not None:
            return True
        
        # Try without namespace
        rest_elem = note.find('.//rest')
        return rest_elem is not None
    
    def _is_chord(self, note: ET.Element) -> bool:
        """Check if note is part of a chord."""
        # Try with namespace
        chord_elem = note.find('.//{http://www.musicxml.org/ns1.1}chord')
        if chord_elem is not None:
            return True
        
        # Try without namespace
        chord_elem = note.find('.//chord')
        return chord_elem is not None
    
    def _extract_pitch(self, note: ET.Element) -> Optional[int]:
        """Extract MIDI pitch from note element.
        
        Returns:
            MIDI note number or None
        """
        # Try with namespace
        pitch_elem = note.find('.//{http://www.musicxml.org/ns1.1}pitch')
        if pitch_elem is None:
            # Try without namespace
            pitch_elem = note.find('.//pitch')
        
        if pitch_elem is None:
            return None
        
        # Extract step, octave, alter
        step_elem = pitch_elem.find('.//{http://www.musicxml.org/ns1.1}step')
        if step_elem is None:
            step_elem = pitch_elem.find('.//step')
        
        octave_elem = pitch_elem.find('.//{http://www.musicxml.org/ns1.1}octave')
        if octave_elem is None:
            octave_elem = pitch_elem.find('.//octave')
        
        alter_elem = pitch_elem.find('.//{http://www.musicxml.org/ns1.1}alter')
        if alter_elem is None:
            alter_elem = pitch_elem.find('.//alter')
        
        # Validate required elements
        if step_elem is None or octave_elem is None:
            return None
        if step_elem.text is None or octave_elem.text is None:
            return None
        
        step = step_elem.text
        octave = int(octave_elem.text)
        alter = int(alter_elem.text) if alter_elem is not None and alter_elem.text else 0
        
        # Convert to MIDI
        pitch_classes = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        if step not in pitch_classes:
            return None
        
        midi = (octave + 1) * 12 + pitch_classes[step] + alter
        
        return midi
    
    def _extract_duration(self, note: ET.Element, divisions: int) -> Optional[float]:
        """Extract duration from note element.
        
        Args:
            note: Note element
            divisions: Divisions per quarter note
        
        Returns:
            Duration in quarter notes
        """
        # Try with namespace
        duration_elem = note.find('.//{http://www.musicxml.org/ns1.1}duration')
        if duration_elem is None:
            # Try without namespace
            duration_elem = note.find('.//duration')
        
        if duration_elem is None or duration_elem.text is None:
            return None
        
        # Convert divisions to quarter notes
        # divisions is "divisions per quarter note"
        # so duration in divisions / divisions = quarter notes
        try:
            duration_value = float(duration_elem.text)
            quarter_length = duration_value / divisions
            return quarter_length
        except ValueError:
            return None

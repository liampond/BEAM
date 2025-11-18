#!/usr/bin/env python3
"""
Match passages across different music encoding formats by comparing musical content.

This module finds corresponding measures in ABC, MusicXML, and MEI files
by matching them against a reference Humdrum passage. It uses the new modular
parser architecture with time-aware comparison that is immune to voice ordering.

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
from typing import Tuple, Optional
from dataclasses import dataclass

# New modular parsers and comparison
from .format_parsers.humdrum_parser import HumdrumParser
from .format_parsers.abc_parser import ABCParser
from .format_parsers.musicxml_parser import MusicXMLParser
from .format_parsers.mei_parser import MEIParser
from .comparison import signatures_match
from .signature import MusicalSignature


@dataclass
class MatchingConfig:
    """Configuration for passage matching algorithm."""
    
    # Search window: how many measures before/after to search
    search_window: int = 10
    
    # Matching tolerances (used by comparison module)
    note_count_tolerance: int = 3
    interval_tolerance: int = 1
    chord_count_tolerance: int = 2
    min_notes_for_interval_match: int = 8
    min_matching_intervals: int = 2


class PassageMatcher:
    """
    Matches musical passages across different encoding formats.
    
    Uses Humdrum as the reference format and finds corresponding measures
    in ABC, MusicXML, and MEI by comparing musical signatures.
    
    The new implementation uses:
    - Modular format parsers (one per format)
    - Event-based MusicalSignature representation
    - Time-aware comparison (immune to voice ordering)
    """
    
    reference_signature: MusicalSignature
    
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
        
        # Initialize parsers
        self.humdrum_parser = HumdrumParser()
        self.abc_parser = ABCParser()
        self.musicxml_parser = MusicXMLParser()
        self.mei_parser = MEIParser()
        
        # Extract reference signature
        sig = self.humdrum_parser.extract_signature(
            self.humdrum_file,
            self.start_measure,
            self.end_measure
        )
        
        if sig is None:
            raise ValueError(
                f"Failed to extract signature from {humdrum_file} "
                f"measures {start_measure}-{end_measure}"
            )
        
        self.reference_signature = sig
    
    def find_in_abc(self, abc_file: Path) -> Optional[Tuple[int, int]]:
        """
        Find matching measures in ABC file.
        
        Searches around the Humdrum measure number ±10 measures.
        
        Returns:
            Tuple of (start_measure, end_measure) or None if not found
        """
        # Search window around expected measure
        search_start = max(1, self.start_measure - self.config.search_window)
        search_end = self.start_measure + self.config.search_window
        target_measure_count = self.reference_signature.measure_count
        
        # Try each possible starting measure
        for start_m in range(search_start, search_end + 1):
            end_m = start_m + target_measure_count - 1
            
            try:
                candidate_sig = self.abc_parser.extract_signature(
                    abc_file,
                    start_m,
                    end_m
                )
                
                if candidate_sig and signatures_match(candidate_sig, self.reference_signature):
                    return (start_m, end_m)
                    
            except Exception:
                # Parser might fail on invalid measure range
                continue
        
        return None
    
    def find_in_musicxml(self, xml_file: Path) -> Optional[Tuple[int, int]]:
        """
        Find matching measures in MusicXML file.
        
        Searches around the Humdrum measure number ±10 measures.
        
        Returns:
            Tuple of (start_measure, end_measure) or None if not found
        """
        search_start = max(1, self.start_measure - self.config.search_window)
        search_end = self.start_measure + self.config.search_window
        target_measure_count = self.reference_signature.measure_count
        
        for start_m in range(search_start, search_end + 1):
            end_m = start_m + target_measure_count - 1
            
            try:
                candidate_sig = self.musicxml_parser.extract_signature(
                    xml_file,
                    start_m,
                    end_m
                )
                
                if candidate_sig and signatures_match(candidate_sig, self.reference_signature):
                    return (start_m, end_m)
                    
            except Exception:
                continue
        
        return None
    
    def find_in_mei(self, mei_file: Path) -> Optional[Tuple[int, int]]:
        """
        Find matching measures in MEI file.
        
        Searches around the Humdrum measure number ±10 measures.
        
        Returns:
            Tuple of (start_measure, end_measure) or None if not found
        """
        search_start = max(1, self.start_measure - self.config.search_window)
        search_end = self.start_measure + self.config.search_window
        target_measure_count = self.reference_signature.measure_count
        
        for start_m in range(search_start, search_end + 1):
            end_m = start_m + target_measure_count - 1
            
            try:
                candidate_sig = self.mei_parser.extract_signature(
                    mei_file,
                    start_m,
                    end_m
                )
                
                if candidate_sig and signatures_match(candidate_sig, self.reference_signature):
                    return (start_m, end_m)
                    
            except Exception:
                continue
        
        return None


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

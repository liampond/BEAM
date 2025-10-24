#!/usr/bin/env python3
"""
Extract musical passages from encoding files.

This module provides both:
1. Library functions for extracting passages programmatically (for benchmark runner)
2. CLI tool for manual inspection and testing

Library usage:
    from src.extract_passage import extract
    
    content = extract(
        format="mei",
        file_path="data/mei/16-1.mei", 
        start_measure=1,
        end_measure=4
    )

CLI usage:
    python extract_passage.py --sonata 16 --movement 1 --measures 1-4
    python extract_passage.py --sonata 16 --movement 1 --measures 5 --format mei
    python extract_passage.py --sonata 16 --movement 1 --measures 1-4 --output excerpt.abc
"""

import argparse
import re
from pathlib import Path
from typing import Optional

# Base paths
DATA_DIR = Path(__file__).parent.parent / "data"


def extract_abc(file_path: Path, start_measure: int, end_measure: int) -> str:
    """
    Extract measures from ABC file with full headers.
    
    Returns the extracted content as a string.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Separate header from body
    header_lines = []
    body_lines = []
    in_body = False
    
    for line in lines:
        # Body starts after K: (key signature) line
        if line.startswith('K:'):
            header_lines.append(line)
            in_body = True
        elif not in_body:
            header_lines.append(line)
        else:
            body_lines.append(line)
    
    # Add a note indicating the extracted measure range
    measure_range_note = f'N: Extracted measures {start_measure}-{end_measure} from original score\n'
    
    # Insert the note after the last N: line or before K: if no N: exists
    header_with_note = []
    note_inserted = False
    for i, line in enumerate(header_lines):
        header_with_note.append(line)
        # Insert our note after the last N: line, or just before K: line
        if line.startswith('K:') and not note_inserted:
            # Insert before K: line
            header_with_note.insert(-1, measure_range_note)
            note_inserted = True
    
    if not note_inserted:
        header_with_note.append(measure_range_note)
    
    # Extract measures from body
    # ABC typically has 2 voices (RH and LH), so each measure = 2 lines
    # Count voice 1 lines with bar markers to determine measures
    extracted_lines = []
    current_measure = 0
    
    for line in body_lines:
        # Check if this is a voice 1 line (contains notes/rests and bar marker)
        if line.startswith('[V:1]'):
            # This is a voice 1 line - increment measure on bar marker
            if '|' in line:
                current_measure += 1
            
            if start_measure <= current_measure <= end_measure:
                extracted_lines.append(line)
        elif line.startswith('[V:2]'):
            # This is voice 2 - include if we're in the measure range
            if start_measure <= current_measure <= end_measure:
                extracted_lines.append(line)
        else:
            # Non-voice lines (e.g., clef changes) - include if in range
            if start_measure <= current_measure <= end_measure:
                extracted_lines.append(line)
    
    result = ''.join(header_with_note) + ''.join(extracted_lines)
    return result


def extract_mei(file_path: Path, start_measure: int, end_measure: int) -> str:
    """
    Extract measures from MEI file with complete header and scoreDef.
    
    Returns the extracted content as a string.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract everything before <music>
    music_start = content.find('<music>')
    if music_start == -1:
        raise ValueError("Could not find <music> tag in MEI file")
    
    header_section = content[:music_start].strip()
    
    # Find scoreDef (contains staffDef with clef, key, meter)
    scoredef_match = re.search(r'<scoreDef.*?</scoreDef>', content, re.DOTALL)
    scoredef = scoredef_match.group(0) if scoredef_match else ''
    
    # Find requested measures
    extracted_measures = []
    for measure_num in range(start_measure, end_measure + 1):
        # Find measure with n="X" attribute
        pattern = rf'<measure[^>]*\bn=["\' ]{measure_num}["\' ][^>]*>.*?</measure>'
        measure_match = re.search(pattern, content, re.DOTALL)
        if measure_match:
            extracted_measures.append(measure_match.group(0))
    
    # Build complete MEI document with header
    # Add proper indentation and newlines between measures
    measures_formatted = '\n            '.join(extracted_measures)
    
    result = f"""{header_section}
  <music>
    <body>
      <mdiv>
        <score>
          {scoredef}
          <section>
            {measures_formatted}
          </section>
        </score>
      </mdiv>
    </body>
  </music>
</mei>
"""
    return result


def extract_musicxml(file_path: Path, start_measure: int, end_measure: int) -> str:
    """
    Extract measures from MusicXML file with attributes.
    
    Returns the extracted content as a string.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract XML header
    xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n'
    
    # Find score-partwise opening with attributes
    partwise_match = re.search(r'<score-partwise[^>]*>', content)
    partwise_tag = partwise_match.group(0) if partwise_match else '<score-partwise>'
    
    # Find part-list (defines instruments)
    partlist_match = re.search(r'<part-list>.*?</part-list>', content, re.DOTALL)
    partlist = partlist_match.group(0) if partlist_match else '<part-list></part-list>'
    
    # Get the first measure to extract attributes (key, time, clef)
    first_measure_match = re.search(r'<measure[^>]*>.*?<attributes>.*?</attributes>.*?</measure>', content, re.DOTALL)
    attributes_xml = ''
    if first_measure_match:
        attr_match = re.search(r'<attributes>.*?</attributes>', first_measure_match.group(0), re.DOTALL)
        if attr_match:
            attributes_xml = attr_match.group(0)
    
    # Extract requested measures
    extracted_measures = []
    measure_pattern = r'<measure[^>]*number=["\'](\d+)["\'][^>]*>.*?</measure>'
    
    for match in re.finditer(measure_pattern, content, re.DOTALL):
        measure_num = int(match.group(1))
        if start_measure <= measure_num <= end_measure:
            measure_xml = match.group(0)
            # Add attributes to first extracted measure if it doesn't have them
            if measure_num == start_measure and '<attributes>' not in measure_xml and attributes_xml:
                # Insert attributes after <measure> tag
                measure_xml = re.sub(r'(<measure[^>]*>)', rf'\1\n      {attributes_xml}', measure_xml)
            extracted_measures.append(measure_xml)
    
    # Build minimal MusicXML document
    result = f"""{xml_header}
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
{partwise_tag}
  {partlist}
  <part id="P1">
    {''.join(extracted_measures)}
  </part>
</score-partwise>
"""
    return result


def extract_humdrum(file_path: Path, start_measure: int, end_measure: int) -> str:
    """
    Extract measures from Humdrum file with all headers and interpretations.
    
    Returns the extracted content as a string.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Collect all reference records (!!!) and global comments
    header_lines = []
    spine_def_lines = []
    measure_lines = []
    
    current_measure = 0
    in_measures = False
    found_spine_def = False
    
    for line in lines:
        line = line.rstrip('\n')
        
        # Reference records and global comments always included
        if line.startswith('!!!'):
            header_lines.append(line)
            continue
        
        # Spine definitions (**kern, etc.) and initial interpretations
        if line.startswith('**'):
            spine_def_lines.append(line)
            found_spine_def = True
            continue
        
        # Tandem interpretations (clef, key, time) before first measure
        if found_spine_def and not in_measures and line.startswith('*'):
            spine_def_lines.append(line)
            continue
        
        # Measure markers
        if line.startswith('='):
            # Extract measure number
            measure_marker = line.split('\t')[0]  # First column
            if measure_marker.startswith('='):
                try:
                    # Handle =1-, =2, etc.
                    num_str = measure_marker[1:].rstrip('-').split()[0]
                    if num_str and num_str.isdigit():
                        current_measure = int(num_str)
                except (ValueError, IndexError):
                    pass
            
            in_measures = True
            
            # Check if this measure is in our range
            if start_measure <= current_measure <= end_measure:
                measure_lines.append(line)
            elif current_measure > end_measure:
                break
            continue
        
        # Data lines within measure range
        if in_measures and start_measure <= current_measure <= end_measure:
            measure_lines.append(line)
    
    # Build complete Humdrum file
    result_lines = header_lines + [''] + spine_def_lines + [''] + measure_lines + ['*-\t*-\t*-']
    result = '\n'.join(result_lines) + '\n'
    return result


def extract(format: str, file_path: str, start_measure: int, end_measure: int) -> str:
    """
    Main extraction function - routes to format-specific extractors.
    
    Args:
        format: One of 'abc', 'mei', 'musicxml', 'humdrum'
        file_path: Path to the source file
        start_measure: First measure to extract (1-indexed)
        end_measure: Last measure to extract (inclusive)
    
    Returns:
        String containing the extracted passage with all metadata
    
    Raises:
        ValueError: If format is not supported
        FileNotFoundError: If file doesn't exist
    """
    path = Path(file_path)
    
    extractors = {
        'abc': extract_abc,
        'mei': extract_mei,
        'musicxml': extract_musicxml,
        'humdrum': extract_humdrum,
    }
    
    if format not in extractors:
        raise ValueError(f"Unsupported format: {format}. Must be one of {list(extractors.keys())}")
    
    return extractors[format](path, start_measure, end_measure)


# ============================================================================
# CLI Interface (for manual testing and inspection)
# ============================================================================

def cli_extract_and_display(format: str, file_path: Path, start_measure: int, 
                           end_measure: int, output_path: Optional[Path] = None):
    """CLI wrapper that extracts and displays/saves results."""
    print(f"\n[{format.upper()}] Extracting measures {start_measure}-{end_measure} from {file_path.name}")
    print("-" * 60)
    
    try:
        result = extract(format, str(file_path), start_measure, end_measure)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(result)
            print(f"Saved to: {output_path}")
            # Count measures for verification
            if format == 'humdrum':
                measure_count = result.count('\n=')
            elif format == 'musicxml':
                measure_count = result.count('<measure')
            elif format == 'mei':
                measure_count = result.count('<measure')
            elif format == 'abc':
                # Count V:1 lines with bar markers
                measure_count = sum(1 for line in result.split('\n') if line.startswith('[V:1]') and '|' in line)
            print(f"Extracted {measure_count} measures")
        else:
            # Display to console
            if len(result) > 2000:
                print(result[:2000] + "\n..." + f"\n[Output truncated - {len(result)} total characters]")
            else:
                print(result)
            
    except Exception as e:
        print(f"Error: {e}")
        return


def main():
    parser = argparse.ArgumentParser(description="Extract musical passages from encoding files")
    parser.add_argument("--sonata", type=int, required=True, help="Sonata number (1-18)")
    parser.add_argument("--movement", type=int, required=True, help="Movement number (1-3)")
    parser.add_argument("--measures", required=True, help="Measure range (e.g., '1-4' or '5')")
    parser.add_argument("--format", choices=["abc", "mei", "musicxml", "humdrum", "all"], 
                       default="all", help="Which format to extract from")
    parser.add_argument("--output", help="Output file path (only works with single format)")
    
    args = parser.parse_args()
    
    # Parse measure range
    if '-' in args.measures:
        start, end = map(int, args.measures.split('-'))
    else:
        start = end = int(args.measures)
    
    print("="*60)
    print(f"EXTRACTING: Sonata {args.sonata}, Movement {args.movement}, Measures {start}-{end}")
    print("="*60)
    
    # File paths
    formats_to_extract = {
        "abc": (DATA_DIR / "abc" / f"{args.sonata:02d}-{args.movement}.abc", "abc"),
        "mei": (DATA_DIR / "mei" / f"{args.sonata:02d}-{args.movement}.mei", "mei"),
        "musicxml": (DATA_DIR / "musicxml" / f"{args.sonata:02d}-{args.movement}.xml", "musicxml"),
        "humdrum": (DATA_DIR / "humdrum" / f"{args.sonata:02d}-{args.movement}.krn", "humdrum"),
    }
    
    if args.output and args.format == "all":
        print("Error: --output can only be used with a specific format, not 'all'")
        return
    
    if args.format == "all":
        for fmt, (file_path, format_name) in formats_to_extract.items():
            cli_extract_and_display(format_name, file_path, start, end, None)
    else:
        file_path, format_name = formats_to_extract[args.format]
        output_path = Path(args.output) if args.output else None
        cli_extract_and_display(format_name, file_path, start, end, output_path)
    
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("- Verify these excerpts render correctly in music notation software")
    print("- Humdrum: Use Verovio or VerovioHumdrum Viewer")
    print("- MusicXML/MEI: Use MuseScore, Finale, or online viewers")
    print("- ABC: Use abcm2ps or EasyABC")
    print("="*60)


if __name__ == "__main__":
    main()

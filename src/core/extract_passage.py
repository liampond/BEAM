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


def _get_mei_measure_offset(file_path: Path) -> int:
    """Return the lowest numeric measure label found in the MEI file."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.parse(file_path).getroot()
    except ET.ParseError:
        return 1

    ns = {'mei': 'http://www.music-encoding.org/ns/mei'}
    min_value = None
    for measure in root.findall('.//mei:measure', ns):
        n = measure.get('n')
        if not n:
            continue
        try:
            value = int(n)
        except ValueError:
            continue
        if min_value is None or value < min_value:
            min_value = value
            if min_value == 0:
                break
    return 1 if min_value is None else min_value


def _human_to_mei(measure_number: int, offset: int) -> int:
    """Convert a human-facing measure number to an MEI-labelled one."""
    if measure_number is None:
        return None
    return measure_number + offset - 1


def _get_musicxml_measure_offset(file_path: Path) -> int:
    """Return lowest numeric measure label in MusicXML file."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.parse(file_path).getroot()
    except ET.ParseError:
        return 1

    # MusicXML 3.1 default namespace
    measures = root.findall('.//{http://www.musicxml.org/ns1.1}measure') or root.findall('.//measure')
    min_value = None
    for measure in measures:
        number = measure.get('number')
        if not number:
            continue
        try:
            value = int(number)
        except ValueError:
            continue
        if min_value is None or value < min_value:
            min_value = value
            if min_value == 0:
                break
    return 1 if min_value is None else min_value


def _get_humdrum_measure_offset(file_path: Path) -> int:
    """Return lowest numeric measure label in Humdrum file."""
    try:
        with open(file_path, 'r') as handle:
            for line in handle:
                if not line.startswith('='):
                    continue
                # Use regex to find the first number in the measure token
                token = line.split('\t', 1)[0]
                match = re.match(r'^=(\d+)', token)
                if match:
                    value = int(match.group(1))
                    return value if value != 0 else 0
    except FileNotFoundError:
        return 1
    return 1

# Base paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"


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
            # Check for setbarnb directive
            setbarnb_match = re.search(r'\[I:setbarnb\s+(\d+)\]', line)
            if setbarnb_match:
                # Interpret setbarnb on a pickup line as setting the NEXT bar's number
                # So this bar is N-1
                current_measure = int(setbarnb_match.group(1)) - 1
            # This is a voice 1 line - increment measure on bar marker if no setbarnb
            elif '|' in line:
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
    
    # Find all scoreDefs to select the appropriate one
    scoredef_pattern = r'<scoreDef.*?</scoreDef>'
    scoredef_matches = list(re.finditer(scoredef_pattern, content, re.DOTALL))
    
    # Find all measures in the file (document order)
    # This handles cases where measure numbers reset (e.g. multi-movement files)
    measure_pattern = r'<measure[^>]*>.*?</measure>'
    all_measures = list(re.finditer(measure_pattern, content, re.DOTALL))
    
    extracted_measures = []
    first_measure_pos = -1
    
    # Extract requested measures by index (1-based)
    # We use indices instead of n attributes because n attributes may not be unique or sequential
    # For MEI, we need to be careful about measures that are split or have suffixes (like 39a, 39b)
    # The user requests a range like 35-42. In the file, we might have 35, 36, 37, 38, 39a, 39b, 40, 41, 42.
    # We should include all measures that "sound" within that logical range.
    
    # First, map the requested logical range to the actual measure elements
    # We'll iterate through all measures and check their 'n' attribute
    
    measures_to_extract = []
    
    for m in all_measures:
        n_attr = re.search(r'\bn=["\']([^"\']+)["\']', m.group(0))
        if n_attr:
            n_val = n_attr.group(1)
            # Handle suffixes like '39a' -> 39
            n_num_match = re.match(r'^(\d+)', n_val)
            if n_num_match:
                n_num = int(n_num_match.group(1))
                if start_measure <= n_num <= end_measure:
                    measures_to_extract.append(m)
                    # If this measure is the end measure and has a repeat end, 
                    # stop looking to avoid including the second ending (which often shares the number)
                    if n_num == end_measure and 'right="rptend"' in m.group(0):
                        break
    if measures_to_extract:
        # Find the scoreDef before the first extracted measure
        first_measure_pos = measures_to_extract[0].start()
        
        selected_scoredef = ''
        if scoredef_matches:
            for sd in scoredef_matches:
                if sd.start() < first_measure_pos:
                    selected_scoredef = sd.group(0)
                else:
                    break
            # Fallback
            if not selected_scoredef and scoredef_matches:
                selected_scoredef = scoredef_matches[0].group(0)
        
        extracted_measures = [m.group(0) for m in measures_to_extract]
    else:
        # Fallback to index-based extraction if 'n' attributes are missing or weird
        # (This preserves previous behavior for files without proper 'n' numbering)
        for i in range(start_measure - 1, end_measure):
            if 0 <= i < len(all_measures):
                extracted_measures.append(all_measures[i].group(0))
                if first_measure_pos == -1:
                    first_measure_pos = all_measures[i].start()
        
        # Select scoreDef (same logic as before)
        selected_scoredef = ''
        if scoredef_matches:
            if first_measure_pos != -1:
                for sd in scoredef_matches:
                    if sd.start() < first_measure_pos:
                        selected_scoredef = sd.group(0)
                    else:
                        break
            if not selected_scoredef and scoredef_matches:
                selected_scoredef = scoredef_matches[0].group(0)

    # Build complete MEI document with header
    # Add proper indentation and newlines between measures
    measures_formatted = '\n            '.join(extracted_measures)
    
    result = f"""{header_section}
  <music>
    <body>
      <mdiv>
        <score>
          {selected_scoredef}
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
    
    # Find the most recent values for each attribute component
    # Track divisions, key, time, staves, and clefs separately since they can change independently
    measure_pattern = r'<measure[^>]*number=["\'](\d+)["\'][^>]*>(.*?)</measure>'
    
    most_recent = {
        'divisions': None,
        'key': None,
        'time': None,
        'staves': None,
        'clefs': []
    }
    
    for match in re.finditer(measure_pattern, content, re.DOTALL):
        measure_num = int(match.group(1))
        measure_content = match.group(2)
        
        # Stop once we've passed the start measure
        if measure_num > start_measure:
            break
            
        # Look for attributes in this measure and update most recent values
        attr_match = re.search(r'<attributes>.*?</attributes>', measure_content, re.DOTALL)
        if attr_match:
            attr_content = attr_match.group(0)
            
            # Update each component if present
            if '<divisions>' in attr_content:
                div_match = re.search(r'<divisions>.*?</divisions>', attr_content, re.DOTALL)
                if div_match:
                    most_recent['divisions'] = div_match.group(0)
            
            if '<key>' in attr_content:
                key_match = re.search(r'<key>.*?</key>', attr_content, re.DOTALL)
                if key_match:
                    most_recent['key'] = key_match.group(0)
            
            if '<time' in attr_content:  # Changed from '<time>' to '<time' to catch attributes like symbol="common"
                time_match = re.search(r'<time[^>]*>.*?</time>', attr_content, re.DOTALL)
                if time_match:
                    most_recent['time'] = time_match.group(0)
            
            if '<staves>' in attr_content:
                staves_match = re.search(r'<staves>.*?</staves>', attr_content, re.DOTALL)
                if staves_match:
                    most_recent['staves'] = staves_match.group(0)
            
            # Collect all clefs (can have multiple for different staves)
            clef_matches = re.findall(r'<clef[^>]*>.*?</clef>', attr_content, re.DOTALL)
            if clef_matches:
                most_recent['clefs'] = clef_matches
    
    # Build complete attributes from most recent values
    attributes_xml = ''
    if any(most_recent.values()):
        attr_parts = []
        if most_recent['divisions']:
            attr_parts.append(most_recent['divisions'])
        if most_recent['key']:
            attr_parts.append(most_recent['key'])
        if most_recent['time']:
            attr_parts.append(most_recent['time'])
        if most_recent['staves']:
            attr_parts.append(most_recent['staves'])
        if most_recent['clefs']:
            attr_parts.extend(most_recent['clefs'])
        
        if attr_parts:
            attributes_content = '\n        '.join(attr_parts)
            attributes_xml = f'<attributes>\n        {attributes_content}\n        </attributes>'
    
    # Extract requested measures
    extracted_measures = []
    
    for match in re.finditer(measure_pattern, content, re.DOTALL):
        measure_num = int(match.group(1))
        if start_measure <= measure_num <= end_measure:
            measure_xml = match.group(0)
            # Add complete attributes to first extracted measure to ensure context is preserved
            if measure_num == start_measure and attributes_xml:
                # Insert attributes right after the opening <measure> tag
                measure_xml = re.sub(
                    r'(<measure[^>]*>)',
                    rf'\1\n      {attributes_xml}',
                    measure_xml,
                    count=1
                )
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
    
    offset = _get_humdrum_measure_offset(file_path)
    target_start = start_measure + offset - 1
    target_end = end_measure + offset - 1

    # Collect all reference records (!!!) and global comments
    header_lines = []
    spine_def_lines = []
    measure_lines = []
    preamble_lines = []  # Spine manipulations to reach target state
    
    current_measure = 0
    in_measures = False
    found_spine_def = False
    num_spines = 0
    found_target = False  # Track if we've found the target measure
    
    # Track spine state
    current_spines = []
    base_spines = []  # Original spine configuration
    base_interp_lines = []  # Original interpretation lines (before any measure)
    # Track interpretations per spine: list of dicts
    spine_states = []
    
    final_spine_count = 0
    
    def get_interp_type(token):
        if token.startswith('*staff'): return 'staff'
        if token.startswith('*clef'): return 'clef'
        if token.startswith('*k['): return 'keysig'
        if token.startswith('*') and token.endswith(':'): return 'key'
        if token.startswith('*M') and not token.startswith('*MM'): return 'meter'
        if token.startswith('*met'): return 'metcodes'
        if token.startswith('*MM'): return 'tempo'
        if token.startswith('*IC'): return 'instr_class'
        if token.startswith('*part'): return 'part'
        if token.startswith('*I"'): return 'instr_name'
        if token.startswith('*I'): return 'instr_code'
        if token in ('*LH', '*RH'): return 'hand'
        return None
    
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
            # Initialize spine tracking
            current_spines = line.split('\t')
            base_spines = current_spines.copy()  # Save the original configuration
            num_spines = len(current_spines)
            spine_states = [{} for _ in range(num_spines)]
            continue
        
        # Track spine changes and interpretations
        if found_spine_def and line.startswith('*'):
            tokens = line.split('\t')
            
            # Save original interpretation lines (before first measure)
            if not in_measures:
                base_interp_lines.append(line)
            
            # Check if it's a spine manipulator line
            if any(t in ('*^', '*v', '*+', '*-') for t in tokens):
                # Track preamble manipulations if we haven't found target yet
                if in_measures and not found_target:
                    preamble_lines.append(line)
                
                new_spines = []
                new_states = []
                current_idx = 0
                merging = False
                
                for token in tokens:
                    if token == '*^':
                        if current_idx < len(current_spines):
                            spine_type = current_spines[current_idx]
                            state = spine_states[current_idx]
                            new_spines.append(spine_type)
                            new_spines.append(spine_type)
                            new_states.append(state.copy())
                            new_states.append(state.copy())
                            current_idx += 1
                        merging = False
                    elif token == '*+':
                        if current_idx < len(current_spines):
                            spine_type = current_spines[current_idx]
                            state = spine_states[current_idx]
                            new_spines.append(spine_type)
                            new_spines.append(spine_type) # Assuming new spine is same type
                            new_states.append(state.copy())
                            new_states.append({}) 
                            current_idx += 1
                        merging = False
                    elif token == '*v':
                        if current_idx < len(current_spines):
                            spine_type = current_spines[current_idx]
                            state = spine_states[current_idx]
                            if not merging:
                                new_spines.append(spine_type)
                                new_states.append(state.copy()) # Keep first spine's state
                                merging = True
                            current_idx += 1
                    elif token == '*-':
                        current_idx += 1
                        merging = False
                    else:
                        if current_idx < len(current_spines):
                            new_spines.append(current_spines[current_idx])
                            new_states.append(spine_states[current_idx])
                            current_idx += 1
                        merging = False
                
                current_spines = new_spines
                spine_states = new_states
                num_spines = len(current_spines)
            
            else:
                # Regular interpretation line - update states
                for i, token in enumerate(tokens):
                    if i < len(spine_states) and token != '*':
                        itype = get_interp_type(token)
                        if itype:
                            spine_states[i][itype] = token

            # If we are inside the target passage, preserve this line
            if in_measures and target_start <= current_measure <= target_end:
                measure_lines.append(line)
                final_spine_count = num_spines

            # Don't append pre-measure interpretations to spine_def_lines
            # We will reconstruct them at the start of the passage
            continue
        
        # Measure markers
        if line.startswith('='):
            # Extract measure number
            measure_marker = line.split('\t')[0]  # First column
            if measure_marker.startswith('='):
                # Use regex to extract measure number, handling suffixes like -, :|!, etc.
                match = re.match(r'^=(\d+)', measure_marker)
                if match:
                    current_measure = int(match.group(1))
            
            in_measures = True
            
            # Check if this measure is in our range
            if target_start <= current_measure <= target_end:
                # Clear previous content if we find the target measure again
                if found_target and current_measure == target_start:
                    measure_lines = []
                
                # If this is the first line of the target passage, update the header
                if not found_target:
                    # Always use BASE spine configuration for header
                    spine_def_lines = ['\t'.join(base_spines)]
                    
                    # Add original interpretation lines (filtered for non-manipulators)
                    for interp_line in base_interp_lines:
                        interp_tokens = interp_line.split('\t')
                        if not any(t in ('*^', '*v', '*+', '*-') for t in interp_tokens):
                            spine_def_lines.append(interp_line)
                    
                    # If spine count differs, generate manipulators to reach current state
                    base_count = len(base_spines)
                    current_count = len(current_spines)
                    
                    if current_count > base_count:
                        # Need to split spines to reach current state
                        # For piano: typically LH (staff2) splits or RH (staff1) splits
                        # We need to figure out which spine(s) split
                        # Simple heuristic: count kern spines in base vs current
                        base_kern_count = sum(1 for s in base_spines if s == '**kern')
                        current_kern_count = sum(1 for s in current_spines if s == '**kern')
                        
                        if current_kern_count > base_kern_count:
                            # Kern spines split - need to add *^ for each split
                            # Generate a split line
                            # Assuming RH (second spine) splits if we have 3 kern from 2
                            diff = current_count - base_count
                            if diff == 1 and base_kern_count == 2:
                                # One spine split - could be LH or RH
                                # Check spine_states to see which one has duplicated states
                                # For now, assume RH splits (common pattern)
                                split_line = ['*', '*^'] + ['*'] * (len(base_spines) - 2)
                                spine_def_lines.append('\t'.join(split_line))
                
                measure_lines.append(line)
                final_spine_count = num_spines
                found_target = True
            continue
        
        # Data lines and interpretations within measure range
        if in_measures and target_start <= current_measure <= target_end:
            measure_lines.append(line)
            final_spine_count = num_spines
    
    # Build complete Humdrum file with proper spine terminators
    # Use final_spine_count if available, otherwise fallback to num_spines
    count_to_use = final_spine_count if final_spine_count > 0 else num_spines
    spine_terminators = '\t'.join(['*-'] * count_to_use)
    result_lines = header_lines + [''] + spine_def_lines + [''] + measure_lines + [spine_terminators]
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
            measure_count = None
            if format == 'humdrum':
                measure_count = result.count('\n=')
            elif format == 'musicxml':
                measure_count = result.count('<measure')
            elif format == 'mei':
                measure_count = result.count('<measure')
            elif format == 'abc':
                # Count V:1 lines with bar markers
                measure_count = sum(1 for line in result.split('\n') if line.startswith('[V:1]') and '|' in line)
            if measure_count is not None:
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

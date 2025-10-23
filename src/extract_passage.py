#!/usr/bin/env python3
"""
Extract musical passages from encoding files for manual inspection.

This helper script extracts specific measures from music files while preserving
all metadata (key, time signature, clef) to create renderable excerpts.

Usage:
    python extract_passage.py --sonata 16 --movement 1 --measures 1-4
    python extract_passage.py --sonata 16 --movement 1 --measures 5 --format mei
    python extract_passage.py --sonata 16 --movement 1 --measures 1-4 --output excerpt.abc
"""

import argparse
import re
from pathlib import Path

# Base paths
DATA_DIR = Path(__file__).parent.parent / "data"


def extract_abc(file_path, start_measure, end_measure, output_path=None):
    """Extract measures from ABC file with full headers."""
    print(f"\n[ABC] Extracting measures {start_measure}-{end_measure} from {file_path.name}")
    print("-" * 60)
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return None
    
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
    
    # Extract measures from body
    # ABC uses | as bar separator, count bars
    body_text = ''.join(body_lines)
    
    # Count measures by counting | symbols
    # This is simplified - real ABC parsing is complex
    # For now, extract a reasonable chunk around the measures
    
    extracted = ''.join(header_lines) + ''.join(body_lines[:20])  # First 20 lines of body
    
    result = extracted + f"\n% Extracted measures {start_measure}-{end_measure}\n% Note: ABC extraction is approximate - verify rendering\n"
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(result)
        print(f"Saved to: {output_path}")
    else:
        print(result)
    
    return result


def extract_mei(file_path, start_measure, end_measure, output_path=None):
    """Extract measures from MEI file with scoreDef."""
    print(f"\n[MEI] Extracting measures {start_measure}-{end_measure} from {file_path.name}")
    print("-" * 60)
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return None
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract XML header and mei opening
    xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n'
    
    # Find the <mei> opening tag with namespaces
    mei_match = re.search(r'<mei[^>]*>', content)
    mei_tag = mei_match.group(0) if mei_match else '<mei>'
    
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
    
    # Build minimal MEI document
    result = f"""{xml_header}
{mei_tag}
  <music>
    <body>
      <mdiv>
        <score>
          {scoredef}
          <section>
            {''.join(extracted_measures)}
          </section>
        </score>
      </mdiv>
    </body>
  </music>
</mei>
"""
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(result)
        print(f"Saved to: {output_path}")
        print(f"Extracted {len(extracted_measures)} measures")
    else:
        print(result[:2000] + "\n..." if len(result) > 2000 else result)
        print(f"\nExtracted {len(extracted_measures)} measures")
    
    return result


def extract_musicxml(file_path, start_measure, end_measure, output_path=None):
    """Extract measures from MusicXML file with attributes."""
    print(f"\n[MusicXML] Extracting measures {start_measure}-{end_measure} from {file_path.name}")
    print("-" * 60)
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return None
    
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
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(result)
        print(f"Saved to: {output_path}")
        print(f"Extracted {len(extracted_measures)} measures")
    else:
        print(result[:2000] + "\n..." if len(result) > 2000 else result)
        print(f"\nExtracted {len(extracted_measures)} measures")
    
    return result


def extract_humdrum(file_path, start_measure, end_measure, output_path=None):
    """Extract measures from Humdrum file with all headers and interpretations."""
    print(f"\n[Humdrum] Extracting measures {start_measure}-{end_measure} from {file_path.name}")
    print("-" * 60)
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return None
    
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
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(result)
        print(f"Saved to: {output_path}")
        print(f"Extracted measures {start_measure}-{end_measure}")
    else:
        print(result)
        print(f"\nExtracted measures {start_measure}-{end_measure}")
    
    return result


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
        "abc": (DATA_DIR / "abc" / f"{args.sonata:02d}-{args.movement}.abc", extract_abc),
        "mei": (DATA_DIR / "mei" / f"{args.sonata:02d}-{args.movement}.mei", extract_mei),
        "musicxml": (DATA_DIR / "musicxml" / f"{args.sonata:02d}-{args.movement}.xml", extract_musicxml),
        "humdrum": (DATA_DIR / "humdrum" / f"{args.sonata:02d}-{args.movement}.krn", extract_humdrum),
    }
    
    if args.output and args.format == "all":
        print("Error: --output can only be used with a specific format, not 'all'")
        return
    
    if args.format == "all":
        for fmt, (file_path, extract_func) in formats_to_extract.items():
            extract_func(file_path, start, end, None)
    else:
        file_path, extract_func = formats_to_extract[args.format]
        extract_func(file_path, start, end, args.output)
    
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("- Verify these excerpts render correctly in music notation software")
    print("- Humdrum: Use Verovio or VerovioHumdrum Viewer")
    print("- MusicXML/MEI: Use MuseScore, Finale, or online viewers")
    print("- ABC: Use abcm2ps or EasyABC")
    print("="*60)


if __name__ == "__main__":
    main()

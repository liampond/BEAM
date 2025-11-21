#!/usr/bin/env python3
"""
Export all 8-bar passages to individual files for verification.
Creates files in outputs/8bar_passages/{format}/
"""

import sqlite3
import os
from pathlib import Path

def get_lines_for_measures(filepath, start_measure, end_measure):
    """
    Extract lines from a music file for a specific measure range.
    Returns all lines from the start of start_measure to the end of end_measure.
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Determine file format
    ext = Path(filepath).suffix
    
    if ext == '.krn':
        # Humdrum format - look for =N markers
        result_lines = []
        in_range = False
        
        for line in lines:
            # Always include header lines (comments, interpretations before first data)
            if line.startswith('!!!') or line.startswith('!!'):
                result_lines.append(line)
                continue
            
            # Check for measure marker
            if line.startswith('='):
                try:
                    # Extract measure number
                    measure_str = line.split('=')[1].split()[0].split('\t')[0]
                    # Remove any non-numeric suffixes (like 'a', 'b', etc.)
                    measure_num = int(''.join(c for c in measure_str if c.isdigit()))
                    
                    if measure_num == start_measure:
                        in_range = True
                    elif measure_num > end_measure:
                        # Add terminator
                        result_lines.append('*-\t*-\t*-\n')
                        break
                except (IndexError, ValueError):
                    pass
            
            # Include spine-path indicators and interpretations
            if line.startswith('**') or line.startswith('*'):
                result_lines.append(line)
                continue
            
            # Include data lines if in range
            if in_range:
                result_lines.append(line)
        
        return result_lines
    
    elif ext == '.abc':
        # ABC format - each measure has 2 lines (V:2 then V:1)
        # But the file has alternating voices, so we need to track pairs
        # Count bar markers cumulatively, but a "measure" in ABC = 2 bar markers (one per voice)
        import re
        
        header_lines = []
        music_lines = []
        cumulative_bars = 0  # Total | characters seen
        in_music = False
        
        # Track clefs: voice_id -> clef_name
        current_clefs = {}
        
        for line in lines:
            # Collect header lines
            if line.startswith(('X:', 'T:', 'M:', 'L:', 'Q:', 'C:', 'A:', 'Z:', '%%', '!')):
                header_lines.append(line)
                continue
            
            if line.startswith('%%staves') or line.startswith('K:'):
                header_lines.append(line)
                continue
                
            if line.startswith('V:') and not in_music:
                header_lines.append(line)
                # Try to parse initial clef from header V: line
                match = re.search(r'V:\s*(\d+).*clef=([a-zA-Z]+)', line)
                if match:
                    voice, clef = match.groups()
                    current_clefs[voice] = clef
                continue
            
            # Check if this is a music line
            if line.strip() and not line.startswith('%') and not line.startswith(('X:', 'T:', 'M:', 'L:', 'K:', 'Q:', 'C:', 'A:', 'Z:', '%%', '!', 'V:')):
                in_music = True
                
                # Parse inline clef changes BEFORE processing the line for extraction
                voice_match = re.search(r'\[V:\s*(\d+)\]', line)
                if voice_match:
                    current_voice = voice_match.group(1)
                    clef_matches = re.findall(r'\[K:clef=([a-zA-Z]+)\]', line)
                    if clef_matches:
                        current_clefs[current_voice] = clef_matches[-1]
                
                # Count bars in this line
                bars_in_line = line.count('|')
                
                # Check if this line's bars fall in our target range
                # Measure N spans cumulative bars [(N-1)*2, N*2)
                
                start_cumulative = (start_measure - 1) * 2
                end_cumulative = end_measure * 2
                
                if cumulative_bars >= start_cumulative and cumulative_bars < end_cumulative:
                    # If this is the FIRST line of the extraction, inject current clefs
                    if not music_lines:
                        for v, c in current_clefs.items():
                            music_lines.append(f"[V:{v}] [K:clef={c}]\n")
                    music_lines.append(line)
                
                cumulative_bars += bars_in_line
                
                if cumulative_bars >= end_cumulative:
                    break
        
        return header_lines + music_lines
    
    elif ext == '.xml':
        # MusicXML - look for measure number attributes
        # Need to preserve header, part-list, and part definition
        # Also need to track attributes (divisions, key, time, clef) to inject into first measure
        import re
        
        result_lines = []
        header_lines = []
        measure_lines = []
        
        in_range = False
        found_start = False
        
        # State tracking for attributes
        # We need to persist these values because they might be defined once at the start
        current_state = {
            'divisions': [],
            'key': [],
            'time': [],
            'staves': [],
            'clef': {}  # number -> list of lines
        }
        
        # Temporary buffers for multi-line tags
        in_attributes = False
        current_tag = None
        tag_buffer = []
        
        # Read file content
        with open(filepath, 'r') as f:
            content = f.read()
            
        lines = content.splitlines(keepends=True)
        
        # 1. Extract Header (up to first measure)
        for i, line in enumerate(lines):
            if '<measure' in line:
                break
            header_lines.append(line)
            
        # 2. Scan for attributes and target measures
        for i, line in enumerate(lines):
            # Track attributes blocks to inject later
            if '<attributes>' in line:
                in_attributes = True
                continue
            
            if '</attributes>' in line:
                in_attributes = False
                continue
                
            if in_attributes:
                stripped = line.strip()
                
                # Handle single-line tags
                if stripped.startswith('<divisions>') and stripped.endswith('</divisions>'):
                    current_state['divisions'] = [line]
                    continue
                if stripped.startswith('<staves>') and stripped.endswith('</staves>'):
                    current_state['staves'] = [line]
                    continue
                    
                # Handle multi-line tags start
                if stripped.startswith('<key'):
                    current_tag = 'key'
                    tag_buffer = [line]
                    if stripped.endswith('</key>'): # Single line key
                        current_state['key'] = tag_buffer
                        current_tag = None
                    continue
                elif stripped.startswith('<time'):
                    current_tag = 'time'
                    tag_buffer = [line]
                    if stripped.endswith('</time>'):
                        current_state['time'] = tag_buffer
                        current_tag = None
                    continue
                elif stripped.startswith('<clef'):
                    current_tag = 'clef'
                    tag_buffer = [line]
                    if stripped.endswith('</clef>'):
                        # Extract number
                        match = re.search(r'number="(\d+)"', line)
                        num = match.group(1) if match else '1'
                        current_state['clef'][num] = tag_buffer
                        current_tag = None
                    continue
                    
                # Handle multi-line tags content/end
                if current_tag:
                    tag_buffer.append(line)
                    if stripped.endswith(f'</{current_tag}>'):
                        if current_tag == 'clef':
                            # Extract number from the first line of buffer
                            match = re.search(r'number="(\d+)"', tag_buffer[0])
                            num = match.group(1) if match else '1'
                            current_state['clef'][num] = tag_buffer
                        else:
                            current_state[current_tag] = tag_buffer
                        current_tag = None
                continue

            # Check for measure
            if '<measure' in line:
                match = re.search(r'number="(\d+)"', line)
                if match:
                    measure_num = int(match.group(1))
                    
                    if measure_num == start_measure:
                        in_range = True
                        found_start = True
                        
                        # Start the measure
                        measure_lines.append(line)
                        
                        # Inject synthesized attributes
                        measure_lines.append('      <attributes>\n')
                        if current_state['divisions']:
                            measure_lines.extend(current_state['divisions'])
                        if current_state['key']:
                            measure_lines.extend(current_state['key'])
                        if current_state['time']:
                            measure_lines.extend(current_state['time'])
                        if current_state['staves']:
                            measure_lines.extend(current_state['staves'])
                        # Sort clefs by number
                        for num in sorted(current_state['clef'].keys()):
                            measure_lines.extend(current_state['clef'][num])
                        measure_lines.append('      </attributes>\n')
                            
                    elif measure_num > end_measure:
                        in_range = False
                        break
                    
                    elif in_range:
                        measure_lines.append(line)
                        
                elif in_range:
                    measure_lines.append(line)
            
            elif in_range:
                measure_lines.append(line)

        # Construct result
        result_lines = header_lines + measure_lines
        
        # Add closing tags
        result_lines.append('  </part>\n')
        result_lines.append('</score-partwise>\n')
        
        return result_lines
    
    elif ext == '.mei':
        # MEI format - look for measure n attributes
        # Need to handle nested sections and proper closing tags
        import re
        
        result_lines = []
        header_lines = []
        measure_lines = []
        
        in_range = False
        
        # Read file content
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        # 1. Extract Header (up to first measure)
        # This includes meiHead, music, body, mdiv, score, section...
        # We need to count how many tags are opened so we can close them
        
        open_tags = []
        
        for line in lines:
            if '<measure' in line:
                break
            header_lines.append(line)
            
            # Track tags in order of appearance
            # Match <tag ...>, </tag>, <tag .../>
            # Group 1: '/' if closing
            # Group 2: tag name
            # Group 3: attributes/content
            matches = re.finditer(r'<(/)?([a-zA-Z0-9_]+)((?:\s+[^>]*)?\/?)>', line)
            
            for match in matches:
                is_closing = match.group(1) == '/'
                tag_name = match.group(2)
                attributes = match.group(3)
                
                if is_closing:
                    if open_tags and open_tags[-1] == tag_name:
                        open_tags.pop()
                else:
                    # Check if self-closing (ends with /)
                    if attributes.strip().endswith('/'):
                        continue
                    
                    # Check for void tags
                    if tag_name in ['lb', 'pb', 'sb', 'br', 'hr']:
                        continue
                        
                    open_tags.append(tag_name)
        
        # 2. Extract Measures
        for line in lines:
            if '<measure' in line and ' n="' in line:
                match = re.search(r' n="(\d+)"', line)
                if match:
                    measure_num = int(match.group(1))
                    if measure_num == start_measure:
                        in_range = True
                    elif measure_num > end_measure:
                        in_range = False
                        break
            
            if in_range:
                measure_lines.append(line)
        
        # 3. Construct Result
        result_lines = header_lines + measure_lines
        
        # 4. Close tags in reverse order
        for tag in reversed(open_tags):
            result_lines.append(f'</{tag}>\n')
            
        return result_lines
    
    return []

def main():
    db_path = 'benchmark.db'
    output_base = Path('outputs/8bar_passages')
    
    # Create output directories
    for fmt in ['humdrum', 'abc', 'musicxml', 'mei']:
        (output_base / fmt).mkdir(parents=True, exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all 8-bar passages
    cursor.execute("""
        SELECT passage_id, sonata_number, movement, 
               start_measure_humdrum, end_measure_humdrum
        FROM passages
        WHERE num_measures = 8
        ORDER BY passage_id
    """)
    
    passages = cursor.fetchall()
    conn.close()
    
    print(f"Exporting {len(passages)} 8-bar passages...\n")
    
    for passage_id, sonata_num, movement, start_h, end_h in passages:
        # Build source filenames
        base_name = f"{sonata_num:02d}-{movement}"
        
        print(f"Processing {passage_id} (Sonata {sonata_num}, Mvt {movement}, measures {start_h}-{end_h})...")
        
        # Export Humdrum
        krn_file = Path('data/humdrum') / f"{base_name}.krn"
        if krn_file.exists():
            try:
                lines = get_lines_for_measures(krn_file, start_h, end_h)
                output_file = output_base / 'humdrum' / f"{passage_id}.krn"
                with open(output_file, 'w') as f:
                    f.writelines(lines)
                print(f"  ✓ Exported Humdrum: {output_file}")
            except Exception as e:
                print(f"  ✗ Error exporting Humdrum: {e}")
        else:
            print(f"  ✗ Humdrum file not found: {krn_file}")
        
        # Export ABC (using same measure numbers - may need adjustment)
        abc_file = Path('data/abc') / f"{base_name}.abc"
        if abc_file.exists():
            try:
                lines = get_lines_for_measures(abc_file, start_h, end_h)
                output_file = output_base / 'abc' / f"{passage_id}.abc"
                with open(output_file, 'w') as f:
                    f.writelines(lines)
                print(f"  ✓ Exported ABC (measures {start_h}-{end_h}): {output_file}")
            except Exception as e:
                print(f"  ✗ Error exporting ABC: {e}")
        
        # Export MusicXML (using same measure numbers - may need adjustment)
        xml_file = Path('data/musicxml') / f"{base_name}.xml"
        if xml_file.exists():
            try:
                lines = get_lines_for_measures(xml_file, start_h, end_h)
                output_file = output_base / 'musicxml' / f"{passage_id}.xml"
                with open(output_file, 'w') as f:
                    f.writelines(lines)
                print(f"  ✓ Exported MusicXML (measures {start_h}-{end_h}): {output_file}")
            except Exception as e:
                print(f"  ✗ Error exporting MusicXML: {e}")
        
        # Export MEI (using same measure numbers - may need adjustment)
        mei_file = Path('data/mei') / f"{base_name}.mei"
        if mei_file.exists():
            try:
                lines = get_lines_for_measures(mei_file, start_h, end_h)
                output_file = output_base / 'mei' / f"{passage_id}.mei"
                with open(output_file, 'w') as f:
                    f.writelines(lines)
                print(f"  ✓ Exported MEI (measures {start_h}-{end_h}): {output_file}")
            except Exception as e:
                print(f"  ✗ Error exporting MEI: {e}")
        
        print()
    
    print(f"\n✓ Export complete!")
    print(f"  Files saved to: {output_base}")
    print(f"\nNext steps:")
    print(f"  1. Compare passages across formats to verify the same music")
    print(f"  2. Note any measure number differences between formats")
    print(f"  3. Update database with correct measure numbers for ABC, MusicXML, and MEI")
    print(f"  4. Some formats may need manual adjustment if measure numbering differs")

if __name__ == '__main__':
    main()

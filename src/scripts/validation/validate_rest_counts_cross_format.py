#!/usr/bin/env python3
"""
Validate rest counts across all four music encoding formats (ABC, Humdrum, MusicXML, MEI).
Reports discrepancies where different formats give different rest counts for the same passage.
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.db_utils import get_connection
from src.core.extract_passage import extract
from src.core.passage_analysis import MusicXMLAnalyzer, count_rests
from typing import Any


def count_rests_abc(abc_content: str) -> int:
    """Count visible rests in ABC notation."""
    # ABC rests are represented by 'z' or 'x' (invisible rest, but we count it as visible in ABC context)
    # We need to count only 'z' as visible rests
    # Remove header lines and comments
    lines = abc_content.split('\n')
    music_lines = []
    in_header = True
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('%'):
            continue
        # Headers start with a letter followed by ':'
        if in_header and ':' in line and len(line) > 0 and line[0].isalpha() and line[1] == ':':
            continue
        in_header = False
        music_lines.append(line)
    
    music_content = ' '.join(music_lines)
    
    # Count 'z' followed by optional duration (number or fraction)
    # Pattern: z followed by optional digits, optional /, optional digits
    rest_pattern = r'z\d*(?:/\d*)?'
    matches = re.findall(rest_pattern, music_content)
    return len(matches)


def count_rests_humdrum(humdrum_content: str) -> int:
    """Count visible rests in Humdrum **kern notation."""
    lines = humdrum_content.split('\n')
    rest_count = 0
    
    for line in lines:
        line = line.strip()
        # Skip comments, interpretations, and barlines
        if not line or line.startswith('!') or line.startswith('*') or line.startswith('='):
            continue
        
        # Split by tabs to get individual spine tokens
        tokens = line.split('\t')
        
        for token in tokens:
            # Rests in Humdrum are indicated by 'r' in the token
            # They can have duration prefixes like 4r, 8r, etc.
            if 'r' in token and not token.startswith('*'):
                # Make sure it's actually a rest token (not part of a note name)
                # Rest tokens typically look like: 4r, 8r, 2r, etc.
                if re.match(r'\d+\.?r', token):
                    rest_count += 1
    
    return rest_count


def count_rests_musicxml(musicxml_content: str) -> int:
    """Count visible rests in MusicXML (using passage_analysis module)."""
    from io import StringIO
    import xml.etree.ElementTree as ET
    
    # Parse the XML
    root = ET.fromstring(musicxml_content)
    
    # Create a temporary file-like object for the analyzer
    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(musicxml_content)
        temp_path = Path(f.name)
    
    try:
        analyzer = MusicXMLAnalyzer(temp_path)
        
        # Get all measures
        all_events = []
        for measure_num in sorted(analyzer._measures.keys()):
            measure_data = analyzer.get_measure(measure_num)
            all_events.extend(measure_data.events)
        
        return count_rests(all_events)
    finally:
        temp_path.unlink()


def count_rests_mei(mei_content: str) -> int:
    """Count visible rests in MEI notation."""
    import xml.etree.ElementTree as ET
    
    try:
        root = ET.fromstring(mei_content)
        
        # MEI namespace
        ns = {'mei': 'http://www.music-encoding.org/ns/mei'}
        
        # Find all rest elements
        rests = root.findall('.//mei:rest', ns)
        
        # Filter out invisible rests (similar to MusicXML print-object="no")
        visible_rests = []
        for rest in rests:
            visible = rest.get('visible')
            if visible != 'false':
                visible_rests.append(rest)
        
        return len(visible_rests)
    except Exception as e:
        print(f"Error parsing MEI: {e}")
        return -1


def validate_passage(passage_id: int) -> Dict[str, Any]:
    """
    Validate rest counts across all formats for a given passage.
    Returns a dict with format names as keys and rest counts as values.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get passage info
    cursor.execute("""
        SELECT pc.sonata_number, pc.movement, p.start_measure, p.end_measure
        FROM passages p
        JOIN pieces pc ON p.piece_id = pc.piece_id
        WHERE p.passage_id = ?
    """, (passage_id,))
    
    row = cursor.fetchone()
    if not row:
        return {'error': f'Passage {passage_id} not found'}
    
    sonata, movement, start_measure, end_measure = row
    conn.close()
    
    # Define paths
    data_dir = Path(__file__).parent.parent.parent / "data"
    
    results = {
        'passage_id': f'P-{passage_id:03d}',
        'sonata': sonata,
        'movement': movement,
        'measures': f'{start_measure}-{end_measure}',
    }
    
    # Extract and count rests in each format
    try:
        abc_file = data_dir / "abc" / f"{sonata:02d}-{movement}.abc"
        abc_content = extract('abc', str(abc_file), start_measure, end_measure)
        results['abc'] = count_rests_abc(abc_content)
    except Exception as e:
        results['abc'] = f'ERROR: {e}'
    
    try:
        humdrum_file = data_dir / "humdrum" / f"{sonata:02d}-{movement}.krn"
        humdrum_content = extract('humdrum', str(humdrum_file), start_measure, end_measure)
        results['humdrum'] = count_rests_humdrum(humdrum_content)
    except Exception as e:
        results['humdrum'] = f'ERROR: {e}'
    
    try:
        musicxml_file = data_dir / "musicxml" / f"{sonata:02d}-{movement}.xml"
        musicxml_content = extract('musicxml', str(musicxml_file), start_measure, end_measure)
        results['musicxml'] = count_rests_musicxml(musicxml_content)
    except Exception as e:
        results['musicxml'] = f'ERROR: {e}'
    
    try:
        mei_file = data_dir / "mei" / f"{sonata:02d}-{movement}.mei"
        mei_content = extract('mei', str(mei_file), start_measure, end_measure)
        results['mei'] = count_rests_mei(mei_content)
    except Exception as e:
        results['mei'] = f'ERROR: {e}'
    
    return results


def main():
    """Validate rest counts for all passages with auto-generated questions."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all passages with auto-generated questions (question_id >= 122)
    cursor.execute("""
        SELECT DISTINCT p.passage_id
        FROM passages p
        JOIN questions q ON p.passage_id = q.passage_id
        WHERE q.question_id >= 122
        ORDER BY p.passage_id
    """)
    
    passage_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"Validating rest counts for {len(passage_ids)} passages across all formats...")
    print("=" * 100)
    
    discrepancies = []
    
    for passage_id in passage_ids:
        results = validate_passage(passage_id)
        
        # Check for discrepancies
        counts = []
        for fmt in ['abc', 'humdrum', 'musicxml', 'mei']:
            if fmt in results and not isinstance(results[fmt], str):
                counts.append(results[fmt])
        
        has_discrepancy = len(set(counts)) > 1 if counts else False
        
        if has_discrepancy or any(isinstance(results.get(fmt), str) for fmt in ['abc', 'humdrum', 'musicxml', 'mei']):
            discrepancies.append(results)
            print(f"\n❌ DISCREPANCY: {results['passage_id']}")
            print(f"   Sonata {results['sonata']}, Movement {results['movement']}, Measures {results['measures']}")
            print(f"   ABC:       {results.get('abc', 'N/A')}")
            print(f"   Humdrum:   {results.get('humdrum', 'N/A')}")
            print(f"   MusicXML:  {results.get('musicxml', 'N/A')}")
            print(f"   MEI:       {results.get('mei', 'N/A')}")
        else:
            print(f"✓ {results['passage_id']}: All formats agree ({counts[0] if counts else 'N/A'} rests)")
    
    print("\n" + "=" * 100)
    if discrepancies:
        print(f"\n⚠️  Found {len(discrepancies)} passage(s) with discrepancies or errors")
        print("\nSummary of discrepancies:")
        for d in discrepancies:
            print(f"  - {d['passage_id']}: ABC={d.get('abc')}, Humdrum={d.get('humdrum')}, "
                  f"MusicXML={d.get('musicxml')}, MEI={d.get('mei')}")
    else:
        print("\n✅ All passages have consistent rest counts across all formats!")


if __name__ == '__main__':
    main()

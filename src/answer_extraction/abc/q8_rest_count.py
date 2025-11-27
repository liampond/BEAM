"""
Q8: How many rests are in this passage?

Respond with a number (e.g., 3).

Rules:
- Count rests across ALL voices/staves
- Count `z` as a rest (visible rest)
- Count `Z` as one rest (multi-measure rest)
- Do NOT count `x` (invisible/spacing rest)
- A rest with duration modifier (e.g., z12, z2) counts as 1 rest
- Rests in tuplets count normally (1 rest each)
"""

import re
from .utils import extract_voice_content, remove_non_note_elements
from ..registry import register_extractor


def count_rests_in_content(content: str) -> int:
    """
    Count rests in ABC content for a single voice.
    
    Counts `z` and `Z` but not `x` (invisible rests).
    Each rest symbol counts as 1 regardless of duration.
    
    Args:
        content: ABC notation content for a voice
        
    Returns:
        Number of rests
    """
    # Remove non-note elements (inline fields, annotations)
    content = remove_non_note_elements(content)
    
    # Handle multi-layer voices (separated by &)
    layers = content.split('&')
    
    total_rests = 0
    
    for layer in layers:
        layer = layer.strip()
        if not layer:
            continue
        
        i = 0
        while i < len(layer):
            char = layer[i]
            
            # Skip grace notes entirely
            if char == '{':
                grace_end = layer.find('}', i)
                if grace_end == -1:
                    grace_end = len(layer)
                i = grace_end + 1
                continue
            
            # Count visible rests (z and Z)
            if char in 'zZ':
                total_rests += 1
                i += 1
                # Skip any duration suffix
                while i < len(layer) and layer[i] in '0123456789/':
                    i += 1
                continue
            
            # Skip invisible rests (x) - don't count them
            if char == 'x':
                i += 1
                # Skip duration suffix
                while i < len(layer) and layer[i] in '0123456789/':
                    i += 1
                continue
            
            i += 1
    
    return total_rests


@register_extractor(8, "abc")
def extract(file_path: str) -> str:
    """
    Count rests in an ABC notation file.
    
    Args:
        file_path: Path to the ABC passage file
    
    Returns:
        The count as a string
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find all voice IDs - capture ID up to ] or space
    voice_pattern = re.compile(r'\[V:\s*([^\]\s]+)')
    voice_ids = list(set(voice_pattern.findall(content)))
    
    if not voice_ids:
        # No explicit voices, treat entire content as single voice
        # Extract just the music content (after K: line)
        lines = content.split('\n')
        music_lines = []
        in_music = False
        for line in lines:
            if line.startswith('K:'):
                in_music = True
                continue
            if in_music and not line.startswith('%') and not line.startswith('['):
                music_lines.append(line)
        music_content = ' '.join(music_lines)
        return str(count_rests_in_content(music_content))
    
    # Count rests across all voices
    total_rests = 0
    for voice_id in voice_ids:
        voice_content = extract_voice_content(content, voice_id)
        total_rests += count_rests_in_content(voice_content)
    
    return str(total_rests)

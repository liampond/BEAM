"""
Q1: How many notes are in the lower staff in this passage?

Include grace notes and ornaments. Count tied notes only once.
Respond with a single number.
"""

import xml.etree.ElementTree as ET
from ..registry import register_extractor

# MEI namespace
MEI_NS = "http://www.music-encoding.org/ns/mei"
NS = {"mei": MEI_NS}


def get_tied_end_note_ids(root: ET.Element) -> set:
    """
    Find all note IDs that are the end of a tie.
    
    These notes should not be counted separately since they are
    continuations of a tied note.
    
    Args:
        root: The MEI document root element
        
    Returns:
        Set of xml:id values for notes that are tie endpoints
    """
    tied_ends = set()
    
    # Find all <tie> elements
    for tie in root.iter(f"{{{MEI_NS}}}tie"):
        endid = tie.get("endid")
        if endid:
            # Remove the leading '#' from the reference
            if endid.startswith("#"):
                endid = endid[1:]
            tied_ends.add(endid)
    
    return tied_ends


def count_notes_in_staff(root: ET.Element, staff_n: str) -> int:
    """
    Count notes in a specific staff, excluding tied note continuations.
    
    Args:
        root: The MEI document root element
        staff_n: The staff number to count (e.g., "1" or "2")
        
    Returns:
        The count of notes
    """
    tied_ends = get_tied_end_note_ids(root)
    count = 0
    
    # Find all staff elements with the specified n attribute
    for staff in root.iter(f"{{{MEI_NS}}}staff"):
        if staff.get("n") != staff_n:
            continue
            
        # Count all notes within this staff
        for note in staff.iter(f"{{{MEI_NS}}}note"):
            note_id = note.get("{http://www.w3.org/XML/1998/namespace}id")
            
            # Skip notes that are tie continuations
            if note_id and note_id in tied_ends:
                continue
                
            count += 1
    
    return count


@register_extractor(1, "mei")
def extract(file_path: str) -> str:
    """
    Count notes in the lower staff (staff 2) of an MEI file.
    
    In MEI, staves are numbered with staff@n attribute.
    Staff 1 is typically the upper staff, staff 2 is the lower.
    
    Includes grace notes. Tied notes are counted only once 
    (the continuation notes are excluded).
    
    Args:
        file_path: Path to the MEI (.mei) passage file
    
    Returns:
        The count as a string
    """
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Lower staff is staff n="2"
    count = count_notes_in_staff(root, "2")
    
    return str(count)

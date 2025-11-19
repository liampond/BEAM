"""
Simple note comparison.

Compares lists of (pitch, duration, is_trill) tuples and reports similarity.
"""

from typing import Dict, List, Tuple, Any


def compare_notes(
    reference_notes: Dict[int, List[Tuple[int, float, bool]]],
    other_notes: Dict[int, List[Tuple[int, float, bool]]],
    duration_tolerance: float = 0.01
) -> Dict[str, Any]:
    """
    Compare two sets of notes by measure.
    
    Args:
        reference_notes: Dict of measure -> [(pitch, duration, is_trill)]
        other_notes: Dict of measure -> [(pitch, duration, is_trill)]
        duration_tolerance: Maximum duration difference to consider a match
    
    Returns:
        Dictionary with comparison results:
        {
            'matches': bool,
            'similarity': float (0.0 to 1.0),
            'total_notes': int,
            'matched_notes': int,
            'measure_details': {...}
        }
    """
    # Check measure coverage
    ref_measures = set(reference_notes.keys())
    other_measures = set(other_notes.keys())
    
    if ref_measures != other_measures:
        return {
            'matches': False,
            'similarity': 0.0,
            'total_notes': sum(len(notes) for notes in reference_notes.values()),
            'matched_notes': 0,
            'error': f"Measure mismatch: reference has {sorted(ref_measures)}, other has {sorted(other_measures)}"
        }
    
    total_notes = 0
    matched_notes = 0
    measure_details = {}
    
    for measure_num in sorted(ref_measures):
        ref_list = reference_notes[measure_num]
        other_list = other_notes[measure_num]
        
        # Sort both lists for comparison
        ref_sorted = sorted(ref_list, key=lambda x: (x[0], x[1]))  # Sort by pitch, then duration
        other_sorted = sorted(other_list, key=lambda x: (x[0], x[1]))
        
        measure_total = len(ref_sorted)
        measure_matched = 0
        
        # Try to match notes
        used_indices = set()
        for ref_note in ref_sorted:
            ref_pitch, ref_dur, ref_trill = ref_note
            
            # Find matching note in other
            for i, other_note in enumerate(other_sorted):
                if i in used_indices:
                    continue
                
                other_pitch, other_dur, other_trill = other_note
                
                # Check if notes match
                if (ref_pitch == other_pitch and
                    abs(ref_dur - other_dur) <= duration_tolerance and
                    ref_trill == other_trill):
                    measure_matched += 1
                    used_indices.add(i)
                    break
        
        total_notes += measure_total
        matched_notes += measure_matched
        
        measure_similarity = measure_matched / measure_total if measure_total > 0 else 0.0
        measure_details[measure_num] = {
            'total': measure_total,
            'matched': measure_matched,
            'similarity': measure_similarity,
            'ref_count': len(ref_sorted),
            'other_count': len(other_sorted)
        }
    
    overall_similarity = matched_notes / total_notes if total_notes > 0 else 0.0
    
    return {
        'matches': overall_similarity >= 0.95,  # 95% threshold
        'similarity': overall_similarity,
        'total_notes': total_notes,
        'matched_notes': matched_notes,
        'measure_details': measure_details
    }


def format_comparison_result(result: Dict) -> str:
    """Format comparison result as human-readable string."""
    if 'error' in result:
        return f"❌ {result['error']}"
    
    similarity_pct = result['similarity'] * 100
    status = "✅ MATCH" if result['matches'] else "❌ NO MATCH"
    
    output = [
        f"{status}: {result['matched_notes']}/{result['total_notes']} notes matched ({similarity_pct:.1f}%)",
        ""
    ]
    
    # Show per-measure details
    measure_details = result.get('measure_details', {})
    if measure_details:
        output.append("Per-measure breakdown:")
        for measure_num in sorted(measure_details.keys()):
            details = measure_details[measure_num]
            m_pct = details['similarity'] * 100
            output.append(
                f"  M{measure_num}: {details['matched']}/{details['total']} matched ({m_pct:.1f}%) "
                f"[ref={details['ref_count']}, other={details['other_count']}]"
            )
    
    return "\n".join(output)

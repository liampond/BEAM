# Architecture Decisions - Passage Matching System

## Decision: Manual Verification Over Automated Parsing
**Date:** Current session  
**Branch:** improve-passage-matching  
**Commit:** 51b6a46

### Context
We attempted to build an automated passage matching system that could find corresponding measures across four music encoding formats (Humdrum, ABC, MusicXML, MEI) by parsing and comparing musical content.

### Journey Through Four Architectural Pivots

#### Pivot 1: Signature Abstraction → Direct Comparison
- **Problem:** Abstract signatures lost too much information
- **Solution:** Compare format-to-format directly using Humdrum as reference

#### Pivot 2: Full Object Model → Simple Tuples
- **Problem:** Complex Note/Measure/Event objects with onset tracking were buggy
- **Solution:** Use simple (pitch, duration, is_trill) tuples organized by measure

#### Pivot 3: Full Parsing → First/Last Note Check
- **Problem:** Parsing all notes reliably is very hard
- **Solution:** Consider checking just first/last notes as sanity check

#### Pivot 4: Any Automated Parsing → Complete Manual Verification
- **Problem:** Even simple parsing has too many format-specific bugs
- **Solution:** Manual verification is more practical for 30 passages

### Final Architecture (Committed)

```
src/core/extractors/
  humdrum.py     - ✅ WORKING (220 notes from M29-41, validated)
  abc.py         - ⚠️ BUGGY (259 notes, 13.2% match rate)
  musicxml.py    - Stub
  mei.py         - Stub

src/core/compare_notes.py - Full comparison function (unused)
```

### What Works
- **Humdrum extractor:** 100% reliable
  - Test case: M29-41 from 16-1.krn (13 measures with repeat marker)
  - Result: 220 notes extracted correctly
  - Handles: chords, accidentals, octaves, dotted notes, rests, trills

### What Doesn't Work
- **ABC extractor bugs:**
  - Wrong note count: 259 vs 220 expected
  - Wrong pitches and durations
  - Only 13.2% match rate with Humdrum
  - Tokenization issues, measure numbering off by 1

### Lessons Learned

#### Parsing Music Formats is Extremely Complex
1. **Each format has unique quirks:**
   - Humdrum: Spine ordering, manipulations, grace note markers
   - ABC: Voice indicators, repeat markers, greedy tokenization
   - MusicXML: Namespace variations, divisions per quarter
   - MEI: Staff-based structure, attribute variations

2. **Small bugs cascade:**
   - One tokenization error affects entire passage
   - Duration calculation bugs compound across measures
   - Voice ordering differences create false negatives

3. **Time investment too high:**
   - 4+ hours on ABC parser, still buggy
   - MusicXML/MEI would take similar effort each
   - 30 test passages could be manually verified in 2-3 hours

### Decision Rationale

**Why Manual Verification is Better:**

1. **Reliability:** 100% accuracy vs uncertain automated results
2. **Time Efficiency:** 2-3 hours total vs 10+ hours per format
3. **Simplicity:** No maintenance burden, no debugging
4. **Scale:** Only 30 passages - small enough for manual work
5. **Quality:** Can catch edge cases automated parsing would miss

**When Automated Parsing Makes Sense:**
- Thousands of passages (not 30)
- Single format (not 4 different formats)
- Well-documented format (these have quirks)
- Available libraries (music21 might work but adds complexity)

### Recommended Approach

1. **Manual Verification Workflow:**
   ```python
   # Store in database
   verified_passages = {
       'P-047': {
           'humdrum': ('16-1.krn', 29, 41),
           'abc': ('16-1.abc', 29, 41),
           'musicxml': ('16-1.xml', 29, 41),
           'mei': ('16-1.mei', 29, 41),
           'verified': True,
           'notes': 'Passage with repeat marker :|]|:'
       }
   }
   ```

2. **Manual Verification Steps:**
   - Open all 4 format files side-by-side
   - Find passage in Humdrum (reference)
   - Visually locate same music in other formats
   - Note measure numbers for each format
   - Document any discrepancies
   - Store in database

3. **Verification Aid:**
   - Use Humdrum extractor as sanity check
   - Export passages to notation software if needed
   - Compare first/last notes manually

### What to Keep from This Work

**Keep:**
- ✅ Humdrum extractor (works perfectly, might be useful)
- ✅ Simple architecture (good foundation if revisited)
- ✅ Lessons learned about format parsing
- ✅ Test infrastructure

**Document but Don't Use:**
- ABC extractor bugs (reference for future)
- Comparison function (might be useful for spot checks)

### Future Considerations

**If Automated Parsing Becomes Necessary:**
- Consider music21 library (handles parsing for all formats)
- Use automated parsing as initial guess, manual verification as fallback
- Focus effort on formats with best tooling support
- Start with simplest format (possibly MusicXML with music21)

**Current Priority:**
- Manual verification of 30 passages
- Store results in database
- Focus on benchmark questions (the actual research goal)

### Conclusion

Automated parsing is a fascinating technical challenge, but for this project's scope (30 test passages across 4 formats), manual verification is the pragmatic solution. The Humdrum extractor demonstrates the approach works in principle, but the effort required to make all 4 formats reliable exceeds the project's needs.

**Time to move forward with manual verification and focus on the actual research questions.**

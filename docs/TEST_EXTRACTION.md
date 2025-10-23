# Passage Extractor Test Results

## Generated Files

I've created 4 test files for Sonata 16, Movement 1, measures 1-4:

1. **test_humdrum.krn** - ✅ Looks good
2. **test_musicxml.xml** - ✅ Looks good  
3. **test_mei.mei** - ✅ Looks good
4. **test_abc.abc** - ⚠️ Shows more than 4 measures (ABC parsing needs work)

## What Each Format Includes

### Humdrum (✅ Complete)
- All reference records (!!!COM, !!!OTL, etc.)
- Spine definitions (**kern, **dynam)
- Tandem interpretations (*clefG2, *k[], *M4/4, etc.)
- Measures 1-4 with bar markers (=1-, =2, =3, =4)
- Proper terminator (*-)

### MusicXML (✅ Complete)
- XML header with DOCTYPE
- part-list with instrument definitions
- attributes (divisions, key, time, staves, clefs)
- All 4 measures with complete note data
- Proper structure

### MEI (✅ Complete)
- XML header with MEI namespace
- scoreDef with staffDef (clefs, key, meter)
- All 4 measure elements with @n="1", @n="2", etc.
- Complete note data with octaves, pitches, durations
- Slurs and beams preserved

### ABC (⚠️ Needs Work)
- All headers included (X:, T:, M:, L:, K:, etc.)
- Voice definitions (V: 1, V: 2)
- Shows ~9 bars instead of 4 (counting is off)

## Testing Recommendations

### 1. Humdrum: test_humdrum.krn
**Online**: https://verovio.humdrum.org/
- Paste the contents of test_humdrum.krn
- Should render first 4 measures correctly

**Command line** (if you have Verovio):
```bash
verovio test_humdrum.krn -o test_humdrum.svg
```

### 2. MusicXML: test_musicxml.xml
**MuseScore** (recommended):
- Open test_musicxml.xml
- Should show 4 measures

**Online**: https://www.soundslice.com/musicxml-viewer/
- Upload test_musicxml.xml

### 3. MEI: test_mei.mei
**Online Verovio Editor**: https://editor.verovio.org/
- Paste contents of test_mei.mei
- Should render 4 measures

### 4. ABC: test_abc.abc
**Online**: https://www.abcjs.net/abcjs-editor.html
- Paste contents of test_abc.abc
- Will probably show more than 4 measures (extraction logic needs improvement)

## What to Check

For each format, verify:
1. ✅ **Key signature** is C major (no sharps/flats)
2. ✅ **Time signature** is 4/4 (common time)
3. ✅ **Clefs** are correct (treble for RH, changes to bass for LH in measure 5 of original)
4. ✅ **Tempo marking** "Allegro" appears
5. ✅ **First note** in RH is C5 (middle C octave)
6. ✅ **Exactly 4 measures** rendered
7. ✅ **Music sounds correct** when played back

## Known Issues

### ABC Format
The ABC extraction is approximate because:
- ABC uses `|` for bar lines but they can appear in multiple contexts
- Counting bars requires full ABC parser
- Current version includes all headers but shows too many measures

**Recommendation**: For now, use ABC files only for full movements, not excerpts. Or manually edit the extracted ABC file to remove extra measures.

### All Formats
- Extractions are structural - layout information (page breaks, spacing) is stripped
- This is intentional for LLM testing - we want just the musical content
- Some metadata (composer, title) might be truncated but key/time/clef are preserved

## Next Steps

1. **Test each file** in the recommended viewers
2. **Report back** which formats render correctly
3. If there are issues, I can:
   - Improve extraction logic
   - Use music21 library for better parsing
   - Adjust what metadata is included

## Quick Test Command

Run all extractions at once:
```bash
python src/extract_passage.py --sonata 16 --movement 1 --measures 1-4 --format all
```

This will show console output for all 4 formats without saving files.

# Source Scripts

This directory contains scripts for downloading and processing Mozart Piano Sonata files.

## Scripts

### import_mei.py
Downloads MEI (Music Encoding Initiative) files from the Digital Mozart Edition (DME).

**Source**: https://dme.mozarteum.at/musik/edition/  
**License**: CC BY-NC-SA 4.0 International  
**Output**: `data/mei/` (53 files)

```bash
python3 src/import_mei.py
```

### import_musicxml.py
Downloads MusicXML files from the DCMLab GitHub repository.

**Source**: https://github.com/DCMLab/schema_annotation_data  
**Output**: `data/musicxml/` (53 files)

```bash
python3 src/import_musicxml.py
```

### import_abc.py
Downloads and splits the combined ABC notation file into individual movement files.

**Source**: https://ifdo.ca/~seymour/kern2abc/mozart_sonatas.abc  
**Output**: `data/abc/` (66 files)

```bash
python3 src/import_abc.py
```

## File Naming Convention

All scripts output files using the standard sonata numbering format:
- `<sonata_number>-<movement>[variation_letter].<extension>`
- Examples: `01-1.mei`, `11-1a.abc`, `06-3m.krn`

## Database Tools

### init_database.py
Initializes the SQLite benchmark database with schema and metadata for all Mozart piano sonatas in the common subset.

**Output**: `benchmark.db` (SQLite database)

```bash
python3 src/init_database.py
```

Creates tables for:
- Pieces (46 active movements from sonatas 1-14, 16, 18)
- Encodings (4 formats per piece: ABC, MEI, MusicXML, Humdrum)
- Passages (musical excerpts for testing)
- Questions (benchmark questions with ground truth)
- Test cases (links questions to specific encodings)
- LLM responses (test results)

### extract_passage.py
Extracts specific measures from music files for manual inspection when writing questions.

```bash
# Extract measures 1-4 from Sonata 16, Movement 1 (all formats)
python3 src/extract_passage.py --sonata 16 --movement 1 --measures 1-4

# Extract from specific format only
python3 src/extract_passage.py --sonata 16 --movement 1 --measures 1-4 --format mei
```

## Notes

- All scripts check for existing files and skip downloads to avoid duplicates
- Scripts use appropriate delays between requests to be respectful to servers
- The MEI script includes K. 533 (Sonata No. 15) which only has 2 movements available
- See `DATABASE.md` for full documentation on the benchmark database structure and workflow

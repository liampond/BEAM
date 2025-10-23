# Mozart Piano Sonatas - LLM Music Encoding Benchmark

This repository contains Mozart's piano sonatas encoded in multiple formats for benchmarking Large Language Model understanding of music notation systems.

## Project Purpose

This benchmark tests which music encoding formats (ABC, MEI, MusicXML, Humdrum) are best understood by LLMs through objective questions about musical content at different granularities (bar, phrase, section, movement).

**See `docs/DATABASE.md` for full benchmark design and `docs/QUICKSTART.md` for usage.**

## Collection Overview

| Format | Files | Coverage | Variations |
|--------|-------|----------|------------|
| **ABC Notation** | 66 | Sonatas 1-14, 16, 18 | Letter suffixes (06-3a-m, 11-1a-g) |
| **MEI** | 53 | All 18 sonatas | No variations, Sonata 15 incomplete |
| **MusicXML** | 53 | All 18 sonatas | No variations, Sonata 15 incomplete |
| **Humdrum** | 66 | Sonatas 1-14, 16, 18 | Letter suffixes (06-3a-m, 11-1a-g) |
| **LilyPond** | 14 | Partial (11, 14, 16) | Letter suffixes (11-1a-f) |

**Missing from all sources**: Sonata 15 movement 3 (revised K. 494), Sonata 17 (K. 570) from ABC/Humdrum

## Repository Structure

```
├── data/                   # Encoded music files
│   ├── abc/               # ABC Notation (66 files)
│   ├── mei/               # MEI format (53 files)
│   ├── musicxml/          # MusicXML format (53 files) - includes harmony annotations
│   ├── humdrum/           # Humdrum format (66 files)
│   └── lilypond/          # LilyPond format (14 files)
├── src/                    # Scripts for data processing and benchmarking
│   ├── download_mei.py     # Download MEI files from DME
│   ├── download_musicxml.py # Download MusicXML from DCMLab
│   ├── split_abc.py        # Download and split ABC file
│   ├── init_database.py    # Initialize benchmark database
│   ├── extract_passage.py  # Extract renderable music excerpts
│   ├── db_utils.py         # Database helper functions
│   ├── example_add_questions.py # Example question creation
│   └── README.md           # Script documentation
├── docs/                   # Documentation
│   ├── DATABASE.md         # Database schema and benchmark design
│   ├── QUICKSTART.md       # Quick reference guide
│   └── TEST_EXTRACTION.md  # Passage extraction testing guide
├── tests/                  # Test outputs and examples
│   ├── test_abc.abc        # Example ABC excerpt
│   ├── test_humdrum.krn    # Example Humdrum excerpt
│   ├── test_mei.mei        # Example MEI excerpt
│   └── test_musicxml.xml   # Example MusicXML excerpt
├── benchmark.db            # SQLite database for LLM benchmarking
└── README.md              # This file
```

## Naming Convention

Files use standard sonata numbering: `<sonata_number>-<movement>[letter_suffix].<extension>`

Examples:
- `01-1.mei` - Sonata No. 1, Movement 1 (MEI format)
- `11-1a.krn` - Sonata No. 11, Movement 1, Variation A (Humdrum format)
- `06-3b.krn` - Sonata No. 6, Movement 3, Variation B (Humdrum format)

## Standard Sonata Numbering

| No. | Key | KV | Composition Date |
|-----|-----|-----|------------------|
| 01 | C major | 279/189d | Munich, Autumn 1774 |
| 02 | F major | 280/189e | Munich, Autumn 1774 |
| 03 | B-flat major | 281/189f | Munich, Autumn 1774 |
| 04 | E-flat major | 282/189g | Munich, Autumn 1774 |
| 05 | G major | 283/189h | Munich, Autumn 1774 |
| 06 | D major | 284/205b | Munich, February–March 1775 |
| 07 | C major | 309/284b | Mannheim, Nov. 8 1777 |
| 08 | A minor | 310/300d | Paris, Summer 1778 |
| 09 | D major | 311/284c | Mannheim, November–December 1777 |
| 10 | C major | 330/300h | Vienna or Salzburg, 1783 |
| 11 | A major | 331/300i | Vienna or Salzburg, 1783 |
| 12 | F major | 332/300k | Vienna or Salzburg, 1783 |
| 13 | B-flat major | 333/315c | Linz, 1783 |
| 14 | C minor | 457 | Vienna, Oct. 14, 1784 |
| 15 | F major | 533/494 | Vienna, Jan. 3, 1788 |
| 16 | C major | 545 | Vienna, Jun. 26, 1788 ("facile") |
| 17 | B-flat major | 570 | Vienna, February, 1789 |
| 18 | D major | 576 | Vienna, July 1789 |

## Sources

### MEI (Music Encoding Initiative)
- **Source**: https://dme.mozarteum.at/musik/edition/
- **Provider**: Digital Mozart Edition (DME), Digital-interactive Mozart-Edition (DIME)
- **License**: CC BY-NC-SA 4.0 International
- **Download**: Automated scraper (`scrape_mei.py`)
- **Files**: 53 files (all 18 sonatas, but Sonata 15 missing movement 3)

### MusicXML
- **Source**: https://github.com/DCMLab/schema_annotation_data/tree/master/data/mozart_sonatas/musicxml
- **Provider**: DCMLab schema annotation data repository
- **Download**: Automated scraper (`download_musicxml.py`)
- **Files**: 53 files (all 18 sonatas, but Sonata 15 missing movement 3)
- **Special Feature**: Includes harmonic analysis annotations (Roman numeral chord symbols)

### ABC Notation
- **Source**: https://ifdo.ca/~seymour/kern2abc/mozart_sonatas.abc
- **Provider**: Converted from Humdrum by Craig Stuart Sapp using hum2abc
- **Download**: Downloaded and split using `split_abc.py`
- **Files**: 66 files (same coverage as Humdrum)
  - Includes variations as separate files with letter suffixes
  - Sonata 06 (K. 284) movement 3: 13 variation files (3a-3m)
  - Sonata 11 (K. 331) movement 1: 7 variation files (1a-1g)
- **Missing**: Sonatas 15 (K. 533) and 17 (K. 570) not available

### Humdrum
- **Source**: https://github.com/humdrum-tools/humdrum-data.git
- **Files**: 66 files
  - Includes variations as separate files with letter suffixes
  - Sonata 06 (K. 284) movement 3: 13 variation files (3a-3m)
  - Sonata 11 (K. 331) movement 1: 7 variation files (1a-1g)
- **Missing**: Sonatas 15 (K. 533) and 17 (K. 570) not available in this repository

### LilyPond
- **Source**: https://www.mutopiaproject.org/cgibin/make-table.cgi?Composer=MozartWA
- **Files**: 14 files (partial collection)
- **Note**: Pieces that contained multiple .ly files were merged using Claude Sonnet 4.5 and manually visually verified using Frescobaldi

## Important Notes

### K. 533/494 (Sonata No. 15, Movement 3)

Piano Sonata No. 15 has a unique history:
- **Movements 1-2** (K. 533): Composed in 1788
- **Movement 3**: Originally K. 494 (Rondo in F), composed separately in 1786

Mozart later revised and lengthened K. 494 to serve as the finale of K. 533 in 1788, creating "K. 533/494". However:
- The **standalone original K. 494** (1786 version) is not available in digital encoding formats in our sources
- The **revised/lengthened version** used in K. 533/494 is also not available separately
- Currently, **only movements 1-2** of Sonata No. 15 are included (files `15-1` and `15-2`)

### Spurious Works Removed

**K. Anh. 136** (formerly "Sonata No. 16 in B-flat major" in some older numberings) has been removed from this collection. This work was once attributed to Mozart but is now known to be composed by August Eberhard Müller (1767-1817). It appears in the Köchel catalog appendix (Anhang) for spurious works.

### Format Consistency

All directories contain the same set of authentic Mozart sonatas where available, with consistent numbering across formats. The Humdrum collection is missing Sonatas 15 and 17, while LilyPond is a partial collection.
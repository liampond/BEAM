# Mozart Piano Sonatas - LLM Music Encoding Benchmark# Music Encoding Benchmark - Refactored Architecture# Mozart Piano Sonatas - LLM Music Encoding Benchmark



This repository contains Mozart's piano sonatas encoded in multiple formats for benchmarking Large Language Model understanding of music notation systems.



## Project Purpose## Project OverviewThis repository contains Mozart's piano sonatas encoded in multiple formats for benchmarking Large Language Model understanding of music notation systems.



This benchmark tests which music encoding formats (ABC, MEI, MusicXML, Humdrum) are best understood by LLMs through objective questions about musical content at different granularities (bar, phrase, section, movement).



## Quick StartThis project benchmarks music encoding formats (Humdrum, ABC, MusicXML, MEI) by matching musical passages across formats. The codebase has been completely refactored with a modular, event-based architecture that is immune to voice ordering differences.## Quick Start



### Installation



```bash## Quick Start### Installation

# Clone the repository

git clone https://github.com/liampond/MusicEncodingBenchmark.git

cd MusicEncodingBenchmark

```python```bash

# Create virtual environment

python3 -m venv .venvfrom pathlib import Path# Clone the repository

source .venv/bin/activate  # On Windows: .venv\Scripts\activate

from src.core.passage_matcher import find_passage_in_all_formatsgit clone https://github.com/liampond/MusicEncodingBenchmark.git

# Install dependencies

pip install -r requirements.txtcd MusicEncodingBenchmark



# Copy environment template and add your API keysresults = find_passage_in_all_formats(

cp .env.example .env

# Edit .env and add your API keys    humdrum_file=Path('data/humdrum/01-1.krn'),# Create virtual environment

```

    abc_file=Path('data/abc/01-1.abc'),python3 -m venv .venv

### Running the Benchmark

    musicxml_file=Path('data/musicxml/01-1.musicxml'),source .venv/bin/activate  # On Windows: .venv\Scripts\activate

```bash

# Run with default settings (uses config.yaml)    mei_file=Path('data/mei/01-1.mei'),

python src/cli/run_benchmark.py

    humdrum_start=87,# Install dependencies

# Run specific questions

python src/cli/run_benchmark.py --questions 22 23 24    humdrum_end=87pip install -r requirements.txt



# Run all questions)

python src/cli/run_benchmark.py --all

# Returns: {'humdrum': (87, 87), 'abc': (87, 87), 'mei': (87, 87)}# Copy environment template and add your API keys

# Use custom config

python src/cli/run_benchmark.py --config my_config.yaml```cp .env.example .env

```

# Edit .env and add your API keys

Configuration is managed through `config.yaml`. See the file for all available options.

## Key Improvements (Phase 5 Complete!)```

## Recent Improvements (November 2025)



The passage matching system has been **completely refactored** with a modular, event-based architecture:

### 🎉 Major Achievements### Running the Benchmark

### Key Features

- ✅ **Voice-order-independent matching** - Fixes multi-voice comparison bugs- ✅ **P-051 Bug Fixed**: Voice ordering no longer affects matching

- ✅ **Modular parser architecture** - Each format has dedicated parser

- ✅ **Event-based signatures** - Format-agnostic representation- ✅ **66% Code Reduction**: passage_matcher.py: 734 → 248 lines```bash

- ✅ **77.8% match rate** across formats (14/18 passages)

- ✅ **Comprehensive test suite** - Unit and integration tests- ✅ **100% Modular**: All extraction code moved to dedicated parsers# Run with default settings (uses config.yaml)



### Architecture- ✅ **Clean Organization**: All files properly organized in directoriespython src/cli/run_benchmark.py



```

src/core/format_parsers/

├── signature.py           # MusicalSignature data model### Code Quality# Run specific questions

├── base.py                # BaseParser abstract class

├── humdrum_parser.py      # Humdrum extraction- **passage_matcher.py**: Clean 248-line APIpython src/cli/run_benchmark.py --questions 22 23 24

├── abc_parser.py          # ABC extraction

├── musicxml_parser.py     # MusicXML extraction- **Modular parsers**: 4 independent, testable parsers

└── mei_parser.py          # MEI extraction

- **Type-safe**: Full type annotations throughout# Run all questions

src/core/

├── comparison.py          # Signature matching logic- **Well-tested**: Comprehensive test suitepython src/cli/run_benchmark.py --all

└── passage_matcher.py     # Main API (248 lines, was 734)

```



### Using the Passage Matcher### Test Results# Use custom config



```python- **Overall**: 14/18 formats matched (77.8%)python src/cli/run_benchmark.py --config my_config.yaml

from pathlib import Path

from src.core.passage_matcher import find_passage_in_all_formats- **Single Measures**: 7/8 passages (87.5%)```



results = find_passage_in_all_formats(- **P-051**: ✅ **FIXED** - MEI matches despite voice ordering!

    humdrum_file=Path('data/humdrum/01-1.krn'),

    abc_file=Path('data/abc/01-1.abc'),Configuration is managed through `config.yaml`. See the file for all available options.

    musicxml_file=Path('data/musicxml/01-1.musicxml'),

    mei_file=Path('data/mei/01-1.mei'),## Directory Structure

    humdrum_start=87,

    humdrum_end=87## Project Purpose

)

# Returns: {'humdrum': (87, 87), 'abc': (87, 87), 'mei': (87, 87)}```

```

MusicEncodingBenchmark/This benchmark tests which music encoding formats (ABC, MEI, MusicXML, Humdrum) are best understood by LLMs through objective questions about musical content at different granularities (bar, phrase, section, movement).

## Collection Overview

├── src/core/                      # Core modules (clean & modular)

| Format | Files | Coverage | Variations |

|--------|-------|----------|------------|│   ├── signature.py               # Event-based representation## Collection Overview

| **ABC Notation** | 66 | Sonatas 1-14, 16, 18 | Letter suffixes (06-3a-m, 11-1a-g) |

| **MEI** | 53 | All 18 sonatas | No variations, Sonata 15 incomplete |│   ├── comparison.py              # Time-aware matching

| **MusicXML** | 53 | All 18 sonatas | No variations, Sonata 15 incomplete |

| **Humdrum** | 66 | Sonatas 1-14, 16, 18 | Letter suffixes (06-3a-m, 11-1a-g) |│   ├── passage_matcher.py         # Main API (248 lines!)| Format | Files | Coverage | Variations |

| **LilyPond** | 14 | Partial (11, 14, 16) | Letter suffixes (11-1a-f) |

│   └── format_parsers/            # One parser per format|--------|-------|----------|------------|

**Missing from all sources**: Sonata 15 movement 3 (revised K. 494), Sonata 17 (K. 570) from ABC/Humdrum

│       ├── base.py| **ABC Notation** | 66 | Sonatas 1-14, 16, 18 | Letter suffixes (06-3a-m, 11-1a-g) |

## Repository Structure

│       ├── humdrum_parser.py| **MEI** | 53 | All 18 sonatas | No variations, Sonata 15 incomplete |

```

MusicEncodingBenchmark/│       ├── abc_parser.py| **MusicXML** | 53 | All 18 sonatas | No variations, Sonata 15 incomplete |

├── README.md               # This file

├── config.yaml             # Benchmark configuration│       ├── musicxml_parser.py| **Humdrum** | 66 | Sonatas 1-14, 16, 18 | Letter suffixes (06-3a-m, 11-1a-g) |

├── requirements.txt        # Python dependencies

├── setup.py                # Package installation│       └── mei_parser.py| **LilyPond** | 14 | Partial (11, 14, 16) | Letter suffixes (11-1a-f) |

├── benchmark.db            # SQLite database

││

├── data/                   # Encoded music files

│   ├── abc/                # ABC Notation (66 files)├── tests/                         # Organized test suite**Missing from all sources**: Sonata 15 movement 3 (revised K. 494), Sonata 17 (K. 570) from ABC/Humdrum

│   ├── humdrum/            # Humdrum format (66 files)

│   ├── mei/                # MEI format (53 files)│   ├── parsers/                   # Unit tests for each parser

│   ├── musicxml/           # MusicXML format (53 files)

│   └── lilypond/           # LilyPond format (14 files)│   └── integration/               # Integration & comprehensive tests## Repository Structure

│

├── src/                    # Main source code│

│   ├── cli/                # Command-line interfaces

│   │   ├── run_benchmark.py  # Main benchmark runner├── scripts/                       # Utility scripts```

│   │   └── add_question.py   # Add questions to database

│   ├── core/               # Core business logic│   ├── debug/                     # Debugging toolsMusicEncodingBenchmark/

│   │   ├── format_parsers/   # Modular parser system (NEW)

│   │   ├── db_utils.py       # Database utilities│   └── utilities/                 # Helper scripts├── .env.example            # Environment variables template

│   │   ├── passage_matcher.py # Passage matching (refactored)

│   │   ├── comparison.py     # Signature comparison (NEW)│├── .gitignore              # Git ignore rules

│   │   └── extract_passage.py # Passage extraction

│   ├── llm/                # LLM integration├── docs/                          # Documentation├── README.md               # This file

│   │   ├── evaluator.py      # Response evaluation

│   │   ├── runner.py         # LLM interaction│   └── refactoring/               # Phase documentation├── config.yaml             # Benchmark configuration

│   │   └── integration/      # Provider implementations

│   ├── parsers/            # Legacy parsers│├── requirements.txt        # Python dependencies

│   └── scripts/            # Utility scripts

│├── data/                          # Music files├── setup.py                # Package installation

├── tests/                  # Test suite (NEW organization)

│   ├── parsers/            # Unit tests for each parser│   ├── abc/, humdrum/, mei/, musicxml/, lilypond/├── benchmark.db            # SQLite database

│   └── integration/        # Integration tests

│││

├── scripts/                # Utility scripts

│   ├── debug/              # Debugging tools└── backups/                       # Old code backups├── data/                   # Encoded music files

│   └── utilities/          # Helper scripts

│```│   ├── abc/                # ABC Notation (66 files)

├── docs/                   # Documentation

│   ├── refactoring/        # Refactoring documentation│   ├── humdrum/            # Humdrum format (66 files)

│   └── FILE_INVENTORY.md   # Complete file listing

│## Architecture│   ├── mei/                # MEI format (53 files)

├── prompts/                # Prompt templates

│   └── system_prompt.txt   # System prompt for LLMs│   ├── musicxml/           # MusicXML format (53 files)

│

├── backups/                # Old code for reference### Event-Based Representation│   └── lilypond/           # LilyPond format (14 files)

│

└── outputs/                # Benchmark outputs (gitignored)```python│

    └── {model}/            # Per-model results

```Event(onset=0.0, pitch=60, duration=1.0, voice=1)├── src/                    # Main source code



## Testing```│   ├── cli/                # Command-line interfaces



### Run All Tests- Format-agnostic│   │   ├── run_benchmark.py  # Main benchmark runner

```bash

# Run parser unit tests- Auto-sorted by (onset, pitch)│   │   └── add_question.py   # Add questions to database

python3 tests/parsers/test_humdrum_parser.py

python3 tests/parsers/test_abc_parser.py- Immune to voice ordering│   ├── core/               # Core business logic

python3 tests/parsers/test_musicxml_parser.py

python3 tests/parsers/test_mei_parser.py│   │   ├── db_utils.py       # Database utilities



# Run integration tests### Time-Aware Comparison│   │   └── extract_passage.py # Passage extraction

python3 tests/integration/test_phase4_integration.py

python3 tests/integration/test_all_passages.py```python│   ├── llm/                # LLM integration

```

# These match even though extraction order differs!│   │   ├── evaluator.py      # Response evaluation

### Current Test Results

- ✅ P-001: ABC + MEI matchedHumdrum: [61, 69, 61, 69] (alternating by spine)│   │   ├── runner.py         # LLM interaction

- ✅ P-051: ABC + MEI matched (voice ordering bug FIXED!)

- ✅ Overall: 14/18 passages (77.8%)MEI:     [69, 69, 61, 61] (grouped by staff)│   │   └── integration/      # Provider implementations

- ✅ Single measures: 7/8 (87.5%)

→ Both sorted: [61, 61, 69, 69] ✅ MATCH!│   │       └── base.py       # Base classes & providers

## Development

```│   └── scripts/            # Utility scripts

### Adding New Parsers

1. Create new parser in `src/core/format_parsers/`│       ├── init_database.py  # Database initialization

2. Inherit from `BaseParser`

3. Implement `extract_signature()` method### Modular Parsers│       ├── cleanup/          # Cleanup utilities

4. Return `MusicalSignature` object

5. Add tests in `tests/parsers/`- Clean separation: one parser per format│       └── data_import/      # Data import scripts



### Project Documentation- Easy to test independently│

- **FILE_INVENTORY.md** - Complete file listing and purposes

- **docs/refactoring/** - Refactoring documentation (historical)- Easy to add new formats├── prompts/                # Prompt templates



## Database Schema- All inherit from `FormatParser` base class│   └── system_prompt.txt   # System prompt for LLMs



The SQLite database tracks:│

- Questions (type, difficulty, passage location)

- Responses (model, format, answer, correctness)## Running Tests├── outputs/                # Benchmark outputs (gitignored)

- Metadata (timestamps, latency, token usage)

│   ├── {model}/            # Per-model results

## Contributing

```bash│   │   └── Q-{question}/   # Per-question responses

See individual module documentation for details on:

- Parser architecture# Comprehensive test suite│   └── summary_*.json      # Run summaries

- Comparison logic

- Test procedurespython3 tests/integration/test_all_passages.py│

- Code organization

```

## License

# Integration tests

[Add your license here]

python3 tests/integration/test_phase4_integration.py## Naming Convention

## Acknowledgments



Mozart piano sonata encodings sourced from various public repositories and encoding projects.

# Individual parser testsFiles use standard sonata numbering: `<sonata_number>-<movement>[letter_suffix].<extension>`

python3 tests/parsers/test_humdrum_parser.py

python3 tests/parsers/test_abc_parser.pyExamples:

python3 tests/parsers/test_musicxml_parser.py- `01-1.mei` - Sonata No. 1, Movement 1 (MEI format)

python3 tests/parsers/test_mei_parser.py- `11-1a.krn` - Sonata No. 11, Movement 1, Variation A (Humdrum format)

```- `06-3b.krn` - Sonata No. 6, Movement 3, Variation B (Humdrum format)



## Usage Examples## Standard Sonata Numbering



### Basic Matching| No. | Key | KV | Composition Date |

```python|-----|-----|-----|------------------|

from pathlib import Path| 01 | C major | 279/189d | Munich, Autumn 1774 |

from src.core.passage_matcher import find_passage_in_all_formats| 02 | F major | 280/189e | Munich, Autumn 1774 |

| 03 | B-flat major | 281/189f | Munich, Autumn 1774 |

results = find_passage_in_all_formats(| 04 | E-flat major | 282/189g | Munich, Autumn 1774 |

    humdrum_file=Path('data/humdrum/16-1.krn'),| 05 | G major | 283/189h | Munich, Autumn 1774 |

    abc_file=Path('data/abc/16-1.abc'),| 06 | D major | 284/205b | Munich, February–March 1775 |

    musicxml_file=Path('data/musicxml/16-1.musicxml'),| 07 | C major | 309/284b | Mannheim, Nov. 8 1777 |

    mei_file=Path('data/mei/16-1.mei'),| 08 | A minor | 310/300d | Paris, Summer 1778 |

    humdrum_start=27,| 09 | D major | 311/284c | Mannheim, November–December 1777 |

    humdrum_end=27| 10 | C major | 330/300h | Vienna or Salzburg, 1783 |

)| 11 | A major | 331/300i | Vienna or Salzburg, 1783 |

```| 12 | F major | 332/300k | Vienna or Salzburg, 1783 |

| 13 | B-flat major | 333/315c | Linz, 1783 |

### Using Parsers Directly| 14 | C minor | 457 | Vienna, Oct. 14, 1784 |

```python| 15 | F major | 533/494 | Vienna, Jan. 3, 1788 |

from pathlib import Path| 16 | C major | 545 | Vienna, Jun. 26, 1788 ("facile") |

from src.core.format_parsers.humdrum_parser import HumdrumParser| 17 | B-flat major | 570 | Vienna, February, 1789 |

from src.core.comparison import signatures_match| 18 | D major | 576 | Vienna, July 1789 |



parser = HumdrumParser()## Sources

sig1 = parser.extract_signature(Path('data/humdrum/01-1.krn'), 87, 87)

sig2 = parser.extract_signature(Path('data/humdrum/02-1.krn'), 27, 27)### MEI (Music Encoding Initiative)

- **Source**: https://dme.mozarteum.at/musik/edition/

if signatures_match(sig1, sig2):- **Provider**: Digital Mozart Edition (DME), Digital-interactive Mozart-Edition (DIME)

    print("Passages match!")- **License**: CC BY-NC-SA 4.0 International

```- **Download**: Automated scraper (`scrape_mei.py`)

- **Files**: 53 files (all 18 sonatas, but Sonata 15 missing movement 3)

### Custom Comparison

```python### MusicXML

from src.core.comparison import signatures_match, ComparisonConfig- **Source**: https://github.com/DCMLab/schema_annotation_data/tree/master/data/mozart_sonatas/musicxml

- **Provider**: DCMLab schema annotation data repository

config = ComparisonConfig(- **Download**: Automated scraper (`download_musicxml.py`)

    note_count_tolerance=5,- **Files**: 53 files (all 18 sonatas, but Sonata 15 missing movement 3)

    duration_tolerance_percent=0.30,- **Special Feature**: Includes harmonic analysis annotations (Roman numeral chord symbols)

    min_similarity=0.85

)### ABC Notation

- **Source**: https://ifdo.ca/~seymour/kern2abc/mozart_sonatas.abc

if signatures_match(sig1, sig2, config):- **Provider**: Converted from Humdrum by Craig Stuart Sapp using hum2abc

    print("Match with custom tolerances!")- **Download**: Downloaded and split using `split_abc.py`

```- **Files**: 66 files (same coverage as Humdrum)

  - Includes variations as separate files with letter suffixes

## Key Files  - Sonata 06 (K. 284) movement 3: 13 variation files (3a-3m)

  - Sonata 11 (K. 331) movement 1: 7 variation files (1a-1g)

### Core (248 lines total API!)- **Missing**: Sonatas 15 (K. 533) and 17 (K. 570) not available

- `src/core/passage_matcher.py` - Main API (was 734, now 248 lines)

- `src/core/signature.py` - Event & MusicalSignature classes### Humdrum

- `src/core/comparison.py` - Matching strategies- **Source**: https://github.com/humdrum-tools/humdrum-data.git

- **Files**: 66 files

### Parsers (~1400 lines total)  - Includes variations as separate files with letter suffixes

- `src/core/format_parsers/humdrum_parser.py` (390 lines)  - Sonata 06 (K. 284) movement 3: 13 variation files (3a-3m)

- `src/core/format_parsers/abc_parser.py` (450 lines)    - Sonata 11 (K. 331) movement 1: 7 variation files (1a-1g)

- `src/core/format_parsers/musicxml_parser.py` (280 lines)- **Missing**: Sonatas 15 (K. 533) and 17 (K. 570) not available in this repository

- `src/core/format_parsers/mei_parser.py` (260 lines)

### LilyPond

## Documentation- **Source**: https://www.mutopiaproject.org/cgibin/make-table.cgi?Composer=MozartWA

- **Files**: 14 files (partial collection)

Detailed refactoring documentation in `docs/refactoring/`:- **Note**: Pieces that contained multiple .ly files were merged using Claude Sonnet 4.5 and manually visually verified using Frescobaldi

- `REFACTOR_PLAN.md` - Overall strategy

- `PHASE1_COMPLETE.md` - Foundation## Important Notes

- `PHASE2_COMPLETE.md` - Parser migration

- `PHASE3_COMPLETE.md` - Comparison logic & P-051 fix### K. 533/494 (Sonata No. 15, Movement 3)

- `PHASE4_COMPLETE.md` - Integration

- `PHASE4_SUMMARY.md` - Final resultsPiano Sonata No. 15 has a unique history:

- **Movements 1-2** (K. 533): Composed in 1788

## Development- **Movement 3**: Originally K. 494 (Rondo in F), composed separately in 1786



### Adding a New FormatMozart later revised and lengthened K. 494 to serve as the finale of K. 533 in 1788, creating "K. 533/494". However:

- The **standalone original K. 494** (1786 version) is not available in digital encoding formats in our sources

1. Create parser class inheriting from `FormatParser`- The **revised/lengthened version** used in K. 533/494 is also not available separately

2. Implement `extract_signature()` method- Currently, **only movements 1-2** of Sonata No. 15 are included (files `15-1` and `15-2`)

3. Add to `PassageMatcher` class

4. Write tests### Spurious Works Removed



Example:**K. Anh. 136** (formerly "Sonata No. 16 in B-flat major" in some older numberings) has been removed from this collection. This work was once attributed to Mozart but is now known to be composed by August Eberhard Müller (1767-1817). It appears in the Köchel catalog appendix (Anhang) for spurious works.

```python

from .base import FormatParser### Format Consistency

from ..signature import MusicalSignature

All directories contain the same set of authentic Mozart sonatas where available, with consistent numbering across formats. The Humdrum collection is missing Sonatas 15 and 17, while LilyPond is a partial collection.
class NewFormatParser(FormatParser):
    def extract_signature(self, file_path, start_measure, end_measure):
        # Parse format and create Events
        events = []
        # ... parsing logic ...
        return MusicalSignature(events=events, measure_count=...)
```

### Modifying Matching Logic

Edit `src/core/comparison.py`:
- Adjust `ComparisonConfig` defaults
- Modify matching strategies
- Add new comparison methods

## Installation

```bash
pip install -r requirements.txt
```

## Testing

All tests organized in `tests/` directory:
- Unit tests in `tests/parsers/`
- Integration tests in `tests/integration/`
- 100% of critical functionality tested

## Status

**Production Ready** ✅

- ✅ P-051 voice ordering bug fixed
- ✅ 77.8% match rate (87.5% for single measures)
- ✅ Clean, modular architecture
- ✅ Comprehensive test suite
- ✅ Well documented
- ✅ Type-safe throughout

## Contributing

1. Follow modular architecture
2. Add tests for new features
3. Use type hints
4. Keep functions focused
5. Update documentation

## Refactoring Summary

### Before
- 734-line monolithic passage_matcher.py
- Inline extraction code for all formats
- Voice ordering bugs
- Hard to test and maintain

### After  
- 248-line clean API
- 4 modular parsers (1,400 lines total)
- Event-based architecture
- Voice-order-independent
- Comprehensively tested
- Easy to extend

**Result**: 66% code reduction in main file, much better organization, P-051 fixed!

---

For detailed technical documentation, see `docs/refactoring/`.

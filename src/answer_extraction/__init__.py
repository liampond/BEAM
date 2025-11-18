"""
Answer Extraction Module

This module provides programmatic answer extraction from music encoding formats.

Structure:
    - musicxml/: MusicXML answer extractors
    - abc/: ABC notation answer extractors
    - mei/: MEI (Music Encoding Initiative) answer extractors
    - humdrum/: Humdrum answer extractors

Each format subdirectory contains:
    - Individual extractor modules for each question type
    - _helpers.py: Format-specific parsing utilities
    - __init__.py: Public API exports

Adding New Question Types:
    1. Implement extractor in each format subdirectory
    2. Add extractor to format's __init__.py exports
    3. Update question dispatcher to map question patterns to new extractor
    4. Add tests in tests/answer_extraction/<format>/

Adding New Formats:
    1. Create new format subdirectory
    2. Implement _helpers.py with format-specific parsing
    3. Implement extractors for all question types
    4. Add format to dispatcher and validation scripts
"""

__version__ = "1.0.0"

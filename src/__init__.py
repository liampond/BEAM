"""
Music Encoding Benchmark

A benchmark suite for evaluating LLM performance on music notation parsing tasks
across different encoding formats (ABC, MEI, MusicXML, Humdrum, LilyPond).
"""

__version__ = "0.1.0"
__author__ = "Liam Pond"

# Make common imports available at package level
from .core import db_utils, extract_passage
from .llm_eval import BenchmarkConfig, BenchmarkRunner

__all__ = [
    "db_utils",
    "extract_passage",
    "BenchmarkConfig",
    "BenchmarkRunner",
]

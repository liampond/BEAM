"""BEAM — a Benchmark for Evaluating LLMs on encoded music.

Top-level package. See the root README for the benchmark spec, database
schema, and how the answer-extraction / evaluation modules fit together.
"""

__version__ = "1.0.0"
__author__ = "Liam Pond"

from .core import extract_passage
from .llm_eval import BenchmarkConfig

__all__ = ["extract_passage", "BenchmarkConfig"]

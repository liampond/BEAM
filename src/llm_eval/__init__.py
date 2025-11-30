"""
LLM Evaluation Module

Infrastructure for evaluating LLM performance on music encoding comprehension tasks.

Architecture:
    - config.py: Configuration management with YAML support
    - providers.py: LLM provider implementations with JSON mode support
    - runner.py: Main evaluation runner (sync and batch modes)
    - query.py: Database query builder for flexible test case selection
    - results.py: Results storage, aggregation, and reporting
    - batch.py: Batch API support for OpenAI and Anthropic
"""

from .config import BenchmarkConfig
from .runner import BenchmarkRunner

__all__ = ["BenchmarkConfig", "BenchmarkRunner"]

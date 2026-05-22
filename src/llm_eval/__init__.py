"""LLM evaluation infrastructure (collection frozen).

The submission CLI / runner that produced beam.db has been archived under
_archive/dead_src/llm_eval/. The modules kept here are the ones still
imported by the answer-extraction tests and by analysis code that reads
beam.db.

    - config.py        YAML-backed BenchmarkConfig dataclasses
    - providers.py     per-provider clients (sync send_prompt)
    - batch.py         batch API submit / poll / fetch
    - batch_storage.py crash-safe on-disk record of submitted batch IDs
    - query.py         TestCaseQuery; reads the legacy template DB
    - results.py       ResultsManager; writes the publication tree + beam.db
    - evaluation.py    answer comparison + error categorisation
    - save_response_pair.py  kwarg wrapper over ResultsManager.save_single_result
"""

from .config import BenchmarkConfig

__all__ = ["BenchmarkConfig"]

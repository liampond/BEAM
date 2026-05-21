"""Kwarg-friendly wrapper over ResultsManager.save_single_result.

Retry CLIs call this with raw provider data instead of constructing a
TestResult + BenchmarkConfig + ModelConfig themselves. No validation of its
own: save_single_result is the audited helper and any ResultValidationError
it raises propagates unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import BenchmarkConfig, ModelConfig
from .query import TestCase
from .results import ResultsManager, TestResult


def save_response_pair(
    *,
    model: str,
    provider: str,
    test_case: TestCase,
    raw_response: str,
    extracted_answer: str,
    is_correct: bool,
    timestamp: str,
    batch_id: Optional[str] = None,
    model_version: Optional[str] = None,
    success: bool = True,
    error: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> Path:
    """Save one (raw_response, extracted_answer) pair to the publication tree
    and beam.db. Returns the JSON path that was written.
    """
    config = BenchmarkConfig()
    if project_root is not None:
        config.project_root = Path(project_root)
    config.output.save_to_database = True
    # resume_run_id != None bypasses _save_config_snapshot so we don't litter
    # an empty timestamped outputs/ subdir for each retry call.
    config.output.resume_run_id = "_retry"

    model_config = ModelConfig(provider=provider, name=model, enabled=True)

    result = TestResult(
        question_id=test_case.question_id,
        passage_id=test_case.passage_id,
        format=test_case.format,
        model_name=model,
        provider=provider,
        run_number=1,
        question_text=test_case.question_text,
        expected_answer=test_case.expected_answer,
        extracted_answer=extracted_answer,
        raw_response=raw_response,
        is_correct=is_correct,
        success=success,
        error=error,
        timestamp=timestamp,
        model_version=model_version,
    )

    ResultsManager(config).save_single_result(
        model_config, result, test_case, batch_id=batch_id
    )

    return (
        config.project_root
        / config.output.base_dir
        / test_case.format
        / model
        / f"{test_case.num_measures}bar"
        / test_case.passage_id
        / f"q{test_case.question_type_id}.json"
    )

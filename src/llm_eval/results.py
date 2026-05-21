"""
Results Storage and Reporting

Handles:
    - Saving individual results to files and database
    - Aggregating results across models/formats
    - Generating summary reports (JSON, CSV)
    - Progress persistence for resumption
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import csv
import json
import os
import sqlite3


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON to a .tmp file then os.replace into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


class ResultValidationError(Exception):
    """Raised by ResultsManager.save_single_result when a result fails
    pre-save validation (empty raw_response on success, qid/format/expected
    mismatch). Aborts the save loop so the operator can intervene rather
    than silently dropping the row."""

    def __init__(self, question_id: str, format: str, reason: str):
        self.question_id = question_id
        self.format = format
        self.reason = reason
        super().__init__(f"{question_id} ({format}): {reason}")


@dataclass
class TestResult:
    """Result of a single test case evaluation."""
    
    # Identifiers
    question_id: str
    passage_id: str
    format: str
    model_name: str
    provider: str
    run_number: int = 1  # Which run (1, 2, 3, etc.)
    
    # Question/Answer
    question_text: str = ""
    expected_answer: str = ""
    extracted_answer: str = ""
    raw_response: str = ""
    
    # Evaluation
    is_correct: bool = False
    numeric_error: Optional[float] = None   # |extracted - expected| for numeric Qs
    error_category: str = ""                # Classification of the error type

    # Metadata
    success: bool = True
    error: Optional[str] = None
    duration_seconds: float = 0.0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    timestamp: str = ""
    # Actual checkpoint that responded (e.g. for gemini-3-pro-preview vs. -3.1-).
    # None when the provider doesn't surface it.
    model_version: Optional[str] = None
    
    # Optional (may be large)
    prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    def to_db_row(self) -> tuple:
        """Convert to database row format."""
        return (
            self.question_id,
            self.passage_id,
            self.format,
            self.model_name,
            self.provider,
            self.expected_answer,
            self.extracted_answer,
            self.raw_response,
            self.is_correct,
            self.numeric_error,
            self.error_category,
            self.success,
            self.error,
            self.duration_seconds,
            self.input_tokens,
            self.output_tokens,
            self.timestamp,
        )


class ResultsManager:
    """
    Manages result storage and reporting.
    
    Directory structure:
        outputs/{run_id}/
            config.yaml               # Config snapshot
            summary.json              # Overall summary
            all_results.csv           # Combined CSV for all models
            batch_ids.json            # For batch resumption
            {model_name}/
                summary.json          # Model-level summary
                results.csv           # CSV format for this model
                {format}/
                    Q-001_r1.json     # Individual responses: {question_id}_r{run}.json
                    Q-001_r2.json
                    Q-001_r3.json
    """
    
    def __init__(self, config):
        from .config import BenchmarkConfig
        self.config: BenchmarkConfig = config
        self.output_dir = config.get_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save config snapshot on init (only for new runs)
        if not config.output.resume_run_id:
            self._save_config_snapshot()
    
    def get_existing_result_status(
        self, 
        model_config, 
        format_name: str, 
        question_id: str, 
        run_number: int
    ) -> Optional[bool]:
        """
        Check if a result already exists for this test case.
        
        Returns:
            - True if exists with success=True
            - False if exists with success=False
            - None if doesn't exist
        """
        from .config import ModelConfig
        model_config: ModelConfig = model_config
        
        model_dir = self.output_dir / model_config.display_name
        format_dir = model_dir / format_name
        response_path = format_dir / f"{question_id}_r{run_number}.json"
        
        if not response_path.exists():
            return None
        
        try:
            with open(response_path, 'r') as f:
                result = json.load(f)
                return result.get("success", False)
        except (json.JSONDecodeError, IOError):
            return None
    
    def should_skip_test(
        self,
        model_config,
        format_name: str,
        question_id: str,
        run_number: int,
    ) -> bool:
        """
        Determine if a test should be skipped based on existing results.
        
        Skip if:
            - Result exists with success=True
            - Result exists with success=False AND retry_failed=False
        """
        status = self.get_existing_result_status(
            model_config, format_name, question_id, run_number
        )
        
        if status is None:
            # No existing result, run the test
            return False
        
        if status is True:
            # Successful result exists, skip
            return True
        
        # status is False (failed result)
        # Skip only if we're not retrying failures
        return not self.config.output.retry_failed
    
    def get_skip_stats(
        self,
        model_config,
        test_cases,
        run_number: int,
    ) -> dict:
        """
        Get statistics about which tests will be skipped.
        
        Returns dict with:
            - skip_count: number to skip
            - retry_count: number of failed tests to retry
            - new_count: number of new tests
            - total: total test cases
        """
        skip_count = 0
        retry_count = 0
        new_count = 0
        
        for test_case in test_cases:
            status = self.get_existing_result_status(
                model_config, test_case.format, test_case.question_id, run_number
            )
            
            if status is None:
                new_count += 1
            elif status is True:
                skip_count += 1
            else:  # status is False
                if self.config.output.retry_failed:
                    retry_count += 1
                else:
                    skip_count += 1
        
        return {
            "skip_count": skip_count,
            "retry_count": retry_count,
            "new_count": new_count,
            "total": len(test_cases),
        }
    
    def _save_config_snapshot(self):
        """Save a copy of the config.yaml used for this run."""
        import shutil
        config_source = self.config.project_root / "config.yaml"
        if config_source.exists():
            shutil.copy(config_source, self.output_dir / "config.yaml")
    
    def _validate_result(self, result: "TestResult", test_case=None) -> Optional[str]:
        """Return an error message if the result should not be saved, None if OK.

        Checks:
        - Empty raw_response on a success=True result (provider bug or parse error).
        - question_id / format / expected_answer mismatch against test_case (alignment bug).
        """
        if result.success and not result.raw_response:
            return "empty raw_response with success=True"

        if test_case is not None:
            if result.question_id != test_case.question_id:
                return (
                    f"question_id mismatch: result has {result.question_id!r}, "
                    f"test_case has {test_case.question_id!r}"
                )
            if result.format != test_case.format:
                return (
                    f"format mismatch: result has {result.format!r}, "
                    f"test_case has {test_case.format!r}"
                )
            if result.expected_answer != test_case.expected_answer:
                return (
                    f"expected_answer mismatch: result has {result.expected_answer!r}, "
                    f"test_case has {test_case.expected_answer!r}"
                )

        return None

    def save_single_result(
        self,
        model_config,
        result: "TestResult",
        test_case=None,
        batch_id: Optional[str] = None,
    ) -> None:
        """Atomically save a result. Raises ResultValidationError if validation fails.

        Writes the per-question JSON to the publication tree
        (``outputs/<format>/<model>/<num_measures>bar/<passage_id>/q<qtype>.json``)
        and upserts the row in ``beam.db``. ``test_case`` is required so we can
        resolve ``qtype`` and ``num_measures`` from the submission record rather
        than re-querying the DB. ``batch_id`` round-trips into both the JSON and
        the DB row so audits can trace every saved answer back to its batch.

        Validation failure (alignment mismatch, empty raw_response on success)
        aborts the save with no file or row written — callers should let the
        exception propagate so the operator can intervene (lifecycle stays at
        ``downloaded``, raw_results_*.json on disk, resume re-runs the loop).
        """
        from .config import ModelConfig
        model_config: ModelConfig = model_config

        if test_case is None:
            raise ResultValidationError(
                question_id=result.question_id,
                format=result.format,
                reason="test_case is required to resolve qtype/num_measures",
            )
        if result.run_number != 1:
            raise ResultValidationError(
                question_id=result.question_id,
                format=result.format,
                reason=f"publication path collapses run_number; got run_number={result.run_number}",
            )

        err = self._validate_result(result, test_case)
        if err is not None:
            raise ResultValidationError(
                question_id=result.question_id,
                format=result.format,
                reason=err,
            )

        qtype = test_case.question_type_id
        num_measures = test_case.num_measures
        response_path = (
            self.config.project_root / self.config.output.base_dir
            / result.format / model_config.name / f"{num_measures}bar"
            / result.passage_id / f"q{qtype}.json"
        )
        rel_source_log = str(response_path.relative_to(self.config.project_root))

        data: Dict[str, Any] = {
            "model": result.model_name,
            "format": result.format,
            "passage_id": result.passage_id,
            "qtype": qtype,
            "num_measures": num_measures,
            "question_text": result.question_text,
            "expected_answer": result.expected_answer,
            "extracted_answer": result.extracted_answer,
            "raw_response": result.raw_response,
            "is_correct": result.is_correct,
            "timestamp": result.timestamp,
            "source_log": rel_source_log,
        }
        if result.model_version is not None:
            data["model_version"] = result.model_version
        if batch_id is not None:
            data["batch_id"] = batch_id

        _atomic_write_json(response_path, data)

        if self.config.output.save_to_database:
            self._save_single_to_database(result, qtype, rel_source_log, batch_id)

    def _save_single_to_database(
        self,
        result: TestResult,
        qtype: int,
        source_log: str,
        batch_id: Optional[str],
    ) -> None:
        """Upsert one row into beam.db.llm_responses.

        beam.db lives at the repo root regardless of ``config.output.database``
        (which still names the legacy template DB used for test-case queries).
        Schema PK is (model, format, passage_id, qtype); INSERT OR REPLACE keeps
        retries idempotent.
        """
        db_path = self.config.project_root / "beam.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO llm_responses "
                "(model, format, passage_id, qtype, raw_response, extracted_answer, "
                "is_correct, timestamp, source_log, batch_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result.model_name,
                    result.format,
                    result.passage_id,
                    qtype,
                    result.raw_response,
                    result.extracted_answer,
                    1 if result.is_correct else 0,
                    result.timestamp,
                    source_log,
                    batch_id,
                ),
            )
    
    def save_model_results(
        self,
        model_config,
        results: List[TestResult],
    ):
        """Save all results for a model."""
        from .config import ModelConfig
        model_config: ModelConfig = model_config
        
        model_dir = self.output_dir / model_config.display_name
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model-level summary JSON
        if self.config.output.generate_json_summary:
            json_path = model_dir / "summary.json"
            
            # Calculate per-run statistics
            runs = {}
            for r in results:
                run_num = r.run_number
                if run_num not in runs:
                    runs[run_num] = {"total": 0, "correct": 0}
                runs[run_num]["total"] += 1
                if r.is_correct:
                    runs[run_num]["correct"] += 1
            
            # Calculate consistency stats
            by_question = {}
            for r in results:
                key = (r.question_id, r.format)
                if key not in by_question:
                    by_question[key] = []
                by_question[key].append(r.is_correct)
            
            consistent_correct = sum(1 for v in by_question.values() if all(v))
            consistent_wrong = sum(1 for v in by_question.values() if not any(v))
            inconsistent = sum(1 for v in by_question.values() if any(v) and not all(v))
            
            with open(json_path, 'w') as f:
                json.dump(
                    {
                        "model": model_config.name,
                        "provider": model_config.provider,
                        "total_results": len(results),
                        "unique_questions": len(by_question),
                        "runs_per_question": max(runs.keys()) if runs else 1,
                        "by_run": {
                            f"run_{k}": {"total": v["total"], "correct": v["correct"], 
                                        "accuracy": v["correct"] / v["total"] if v["total"] > 0 else 0}
                            for k, v in sorted(runs.items())
                        },
                        "consistency": {
                            "consistent_correct": consistent_correct,
                            "consistent_wrong": consistent_wrong,
                            "inconsistent": inconsistent,
                        },
                        "overall": {
                            "total": len(results),
                            "correct": sum(1 for r in results if r.is_correct),
                            "accuracy": sum(1 for r in results if r.is_correct) / len(results) if results else 0,
                        },
                    },
                    f,
                    indent=2,
                )
        
        # Save CSV
        if self.config.output.generate_csv_summary:
            csv_path = model_dir / "results.csv"
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "question_id", "passage_id", "format", "run",
                    "expected_answer", "extracted_answer", "is_correct",
                    "success", "duration_seconds",
                ])
                for r in results:
                    writer.writerow([
                        r.question_id, r.passage_id, r.format, r.run_number,
                        r.expected_answer, r.extracted_answer, r.is_correct,
                        r.success, r.duration_seconds,
                    ])
        
        # Note: Individual response files are already saved incrementally via save_single_result()
        # Note: Database entries are already saved incrementally via save_single_result()
    
    def save_summary(self, summary: Dict[str, Any], all_results: Optional[Dict[str, List[TestResult]]] = None):
        """Save overall benchmark summary and combined CSV."""
        summary_path = self.output_dir / "summary.json"
        _atomic_write_json(summary_path, summary)
        
        # Generate combined all_results.csv
        if all_results and self.config.output.generate_csv_summary:
            csv_path = self.output_dir / "all_results.csv"
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "model", "provider", "question_id", "passage_id", "format", "run",
                    "expected_answer", "extracted_answer", "is_correct",
                    "success", "error", "duration_seconds", "input_tokens", "output_tokens",
                ])
                for model_name, results in all_results.items():
                    for r in results:
                        writer.writerow([
                            r.model_name, r.provider, r.question_id, r.passage_id, 
                            r.format, r.run_number,
                            r.expected_answer, r.extracted_answer, r.is_correct,
                            r.success, r.error, r.duration_seconds, 
                            r.input_tokens, r.output_tokens,
                        ])
            print(f"Combined results: {csv_path}")
        
        print(f"\nResults saved to: {self.output_dir}")
        print(f"Summary: {summary_path}")
    
    def generate_comparison_report(self) -> Dict[str, Any]:
        """
        Generate comparison report across all models in this run.
        
        Returns:
            Report with accuracy breakdowns by model, format, question type
        """
        # Load all model results
        all_results = {}
        
        for model_dir in self.output_dir.iterdir():
            if not model_dir.is_dir():
                continue
            
            summary_path = model_dir / "summary.json"
            if summary_path.exists():
                with open(summary_path) as f:
                    all_results[model_dir.name] = json.load(f)
        
        if not all_results:
            return {"error": "No results found"}
        
        # Build comparison
        report = {
            "run_id": self.output_dir.name,
            "models": {},
            "by_format": {},
            "by_question_type": {},
        }
        
        for model_name, data in all_results.items():
            results = data.get("results", [])
            
            report["models"][model_name] = {
                "total": len(results),
                "correct": sum(1 for r in results if r.get("is_correct")),
                "accuracy": sum(1 for r in results if r.get("is_correct")) / len(results) if results else 0,
            }
            
            # By format
            for r in results:
                fmt = r.get("format", "unknown")
                if fmt not in report["by_format"]:
                    report["by_format"][fmt] = {}
                if model_name not in report["by_format"][fmt]:
                    report["by_format"][fmt][model_name] = {"total": 0, "correct": 0}
                
                report["by_format"][fmt][model_name]["total"] += 1
                if r.get("is_correct"):
                    report["by_format"][fmt][model_name]["correct"] += 1
        
        return report

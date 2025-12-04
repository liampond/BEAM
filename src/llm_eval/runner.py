"""
Benchmark Runner

Main orchestration for running LLM benchmarks.

Supports:
    - Synchronous execution (one request at a time)
    - Batch execution (via OpenAI/Anthropic batch APIs)
    - Progress tracking and resumption
    - Comprehensive result collection
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import json
import time
import re

from .config import BenchmarkConfig, ModelConfig
from .providers import get_provider, BaseLLMProvider, LLMResponse
from .query import TestCaseQuery, TestCase, build_prompt
from .batch import BatchRunner, BatchRequest, BatchResult
from .results import ResultsManager, TestResult


class BenchmarkRunner:
    """
    Main benchmark runner.
    
    Orchestrates:
        1. Loading configuration
        2. Fetching test cases
        3. Sending prompts to LLMs
        4. Collecting and storing results
        
    Usage:
        config = BenchmarkConfig.from_yaml("config.yaml")
        runner = BenchmarkRunner(config)
        runner.run()
    """
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.query = TestCaseQuery(config)
        self.results_manager = ResultsManager(config)
        
        # Load system prompt once
        self.system_prompt = config.get_system_prompt()
        
        # Load API keys
        config.load_api_keys()
    
    def run(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Run the benchmark.
        
        Args:
            progress_callback: Optional callback(current, total, message)
            
        Returns:
            Summary statistics
        """
        # Validate configuration
        issues = self.config.validate()
        if issues:
            raise ValueError(f"Configuration issues: {issues}")
        
        # Print configuration summary
        if self.config.execution.verbose:
            print(self.config.summary())
        
        # Fetch test cases
        print("Fetching test cases...")
        test_cases = self.query.fetch_test_cases()
        print(f"Found {len(test_cases)} test cases")
        
        if not test_cases:
            print("No test cases match the filter criteria")
            return {"total": 0, "models": {}}
        
        # Show summary
        summary = self.query.get_summary()
        print(f"  By format: {summary['by_format']}")
        print(f"  By question type: {summary['by_question_type']}")
        
        # Dry run mode
        if self.config.execution.dry_run:
            print("\n[DRY RUN] Would test with:")
            for model in self.config.get_enabled_models():
                print(f"  - {model.provider}/{model.name}")
            return {"dry_run": True, "test_cases": len(test_cases)}
        
        # Resumption mode info
        if self.config.output.resume_run_id:
            print(f"\n[RESUME MODE] Continuing run: {self.config.output.resume_run_id}")
            if self.config.output.retry_failed:
                print("  - Will retry previously failed tests")
            else:
                print("  - Will skip previously failed tests")
        
        # Run tests for each enabled model
        all_results: Dict[str, List[TestResult]] = {}
        enabled_models = self.config.get_enabled_models()
        runs_per_question = self.config.execution.runs_per_question
        
        for model_config in enabled_models:
            print(f"\n{'='*60}")
            print(f"Testing: {model_config.provider}/{model_config.name}")
            if runs_per_question > 1:
                print(f"  ({runs_per_question} runs per question)")
            print(f"{'='*60}")
            
            model_results = []
            
            # Run multiple times if configured
            for run_num in range(1, runs_per_question + 1):
                if runs_per_question > 1:
                    print(f"\n--- Run {run_num}/{runs_per_question} ---")
                
                # Check resumption stats for this run
                if self.config.output.resume_run_id:
                    stats = self.results_manager.get_skip_stats(
                        model_config, test_cases, run_num
                    )
                    print(f"  Resumption: {stats['skip_count']} complete, "
                          f"{stats['retry_count']} to retry, "
                          f"{stats['new_count']} new")
                    
                    if stats['skip_count'] == stats['total']:
                        print("  All tests already complete, skipping...")
                        continue
                
                # Decide: batch vs sync
                # Batch API is enabled per-model via use_batch_api flag
                use_batch = (
                    model_config.use_batch_api and
                    model_config.provider in ("openai", "anthropic", "google", "alibaba")
                )
                
                if use_batch:
                    results = self._run_batch(model_config, test_cases, progress_callback, run_num)
                else:
                    results = self._run_sync(model_config, test_cases, progress_callback, run_num)
                
                model_results.extend(results)
            
            all_results[model_config.name] = model_results
            
            # Save intermediate results
            self.results_manager.save_model_results(model_config, model_results)
        
        # Generate final summary
        final_summary = self._generate_summary(all_results)
        self.results_manager.save_summary(final_summary, all_results)
        
        return final_summary
    
    def _run_sync(
        self,
        model_config: ModelConfig,
        test_cases: List[TestCase],
        progress_callback: Optional[Callable] = None,
        run_number: int = 1,
    ) -> List[TestResult]:
        """Run tests synchronously (one at a time)."""
        
        # Get provider
        # Use 'is not None' to allow explicit 0.0 temperature overrides
        temperature = model_config.temperature if model_config.temperature is not None else self.config.api_settings.temperature
        provider = get_provider(
            provider=model_config.provider,
            model_name=model_config.name,
            temperature=temperature,
            max_tokens=model_config.max_tokens or self.config.api_settings.max_tokens,
            timeout=model_config.timeout or self.config.api_settings.timeout,
            seed=self.config.api_settings.seed,
        )
        
        results = []
        total = len(test_cases)
        skipped = 0
        
        for i, test_case in enumerate(test_cases, 1):
            # Check if we should skip this test (resumption logic)
            if self.results_manager.should_skip_test(
                model_config, test_case.format, test_case.question_id, run_number
            ):
                skipped += 1
                if self.config.execution.show_progress:
                    print(f"  [{i}/{total}] {test_case.question_id} ({test_case.format})... SKIP (already complete)")
                continue
            
            if self.config.execution.show_progress:
                print(f"  [{i}/{total}] {test_case.question_id} ({test_case.format})...", end=" ")
            
            if progress_callback:
                progress_callback(i, total, f"{test_case.question_id} ({test_case.format})")
            
            # Build prompt
            prompt = build_prompt(
                test_case,
                self.system_prompt,
                include_format_hint=self.config.prompt.include_format_hint,
            )
            
            # Send to LLM
            response = self._send_with_retry(
                provider,
                prompt,
                self.system_prompt,
                json_mode=self.config.prompt.enforce_json,
            )
            
            # Evaluate
            result = self._evaluate_response(test_case, model_config, response, prompt, run_number)
            results.append(result)
            
            # Save immediately (incremental saving)
            self.results_manager.save_single_result(model_config, result)
            
            # Print result
            if self.config.execution.show_progress:
                if response.success:
                    status = "✓" if result.is_correct else "✗"
                    extracted = result.extracted_answer[:20] if result.extracted_answer else "N/A"
                    print(f"{status} {extracted} (expected: {test_case.expected_answer})")
                else:
                    print(f"ERROR: {response.error}")
            
            # Rate limiting
            time.sleep(self.config.api_settings.rate_limit_delay)
        
        if skipped > 0:
            print(f"  Skipped {skipped} already-complete tests")
        
        return results
    
    def _run_batch(
        self,
        model_config: ModelConfig,
        test_cases: List[TestCase],
        progress_callback: Optional[Callable] = None,
        run_number: int = 1,
    ) -> List[TestResult]:
        """Run tests using batch API."""
        
        # Filter out already-complete tests for resumption
        tests_to_run = []
        for test_case in test_cases:
            if not self.results_manager.should_skip_test(
                model_config, test_case.format, test_case.question_id, run_number
            ):
                tests_to_run.append(test_case)
        
        if len(tests_to_run) < len(test_cases):
            print(f"  Skipping {len(test_cases) - len(tests_to_run)} already-complete tests")
        
        if not tests_to_run:
            print("  All tests already complete, nothing to submit")
            return []
        
        print(f"  Submitting batch of {len(tests_to_run)} requests...")
        
        # Prepare batch requests
        batch_requests = []
        for test_case in tests_to_run:
            prompt = build_prompt(
                test_case,
                self.system_prompt,
                include_format_hint=self.config.prompt.include_format_hint,
            )
            
            batch_requests.append(BatchRequest(
                custom_id=test_case.custom_id,
                prompt=prompt,
                system_prompt=self.system_prompt,
                metadata={"test_case": test_case},
            ))
        
        # Create batch runner
        # Use 'is not None' to allow explicit 0.0 temperature overrides
        temperature = model_config.temperature if model_config.temperature is not None else self.config.api_settings.temperature
        batch_runner = BatchRunner(
            provider=model_config.provider,
            model_name=model_config.name,
            max_tokens=model_config.max_tokens or self.config.api_settings.max_tokens,
            temperature=temperature,
        )
        
        # Build batch metadata from config for tracking
        batch_metadata = {
            "format": self.config.filters.formats[0] if self.config.filters.formats else "unknown",
            "num_measures": self.config.filters.num_measures[0] if self.config.filters.num_measures else "all",
        }
        # Add question range from config if specified
        if self.config.filters.question_ids:
            q_ids = sorted(self.config.filters.question_ids)
            if len(q_ids) == 1:
                batch_metadata["question_range"] = q_ids[0]
            else:
                batch_metadata["question_range"] = f"{q_ids[0]}-to-{q_ids[-1]}"
        
        # Submit batch
        batch_id = batch_runner.submit(
            batch_requests,
            json_mode=self.config.prompt.enforce_json,
            batch_metadata=batch_metadata,
        )
        print(f"  Batch submitted: {batch_id}")
        
        # Save batch ID for resumption
        if self.config.batch_settings.save_batch_ids:
            self.results_manager.save_batch_id(model_config, batch_id)
        
        # Wait for completion
        def batch_progress(status):
            print(f"  Status: {status.status} ({status.progress_pct:.1f}%)")
        
        batch_results = batch_runner.wait_for_completion(
            batch_id,
            check_interval=self.config.batch_settings.check_interval,
            max_wait_time=self.config.batch_settings.max_wait_time,
            progress_callback=batch_progress,
        )
        
        print(f"  Batch complete: {len(batch_results)} results")
        
        # Map results back to test cases (use tests_to_run, not full test_cases)
        test_case_map = {tc.custom_id: tc for tc in tests_to_run}
        results = []
        
        for batch_result in batch_results:
            test_case = test_case_map.get(batch_result.custom_id)
            if not test_case:
                continue
            
            # Create LLMResponse from batch result
            response = LLMResponse(
                text=batch_result.response_text,
                model=model_config.name,
                provider=model_config.provider,
                success=batch_result.success,
                error=batch_result.error,
                raw_metadata=batch_result.metadata,
            )
            response.extract_json_answer()
            
            # Build prompt for result storage
            prompt = build_prompt(
                test_case,
                self.system_prompt,
                include_format_hint=self.config.prompt.include_format_hint,
            )
            
            result = self._evaluate_response(test_case, model_config, response, prompt, run_number)
            results.append(result)
            
            # Save immediately (incremental saving for batch results too)
            self.results_manager.save_single_result(model_config, result)
        
        return results
    
    def _send_with_retry(
        self,
        provider: BaseLLMProvider,
        prompt: str,
        system_prompt: str,
        json_mode: bool,
    ) -> LLMResponse:
        """Send prompt with retry logic."""
        
        last_error = None
        
        for attempt in range(self.config.execution.max_retries + 1):
            response = provider.send_prompt(
                prompt=prompt,
                system_prompt=system_prompt,
                json_mode=json_mode,
            )
            
            if response.success:
                return response
            
            last_error = response.error
            
            if attempt < self.config.execution.max_retries and self.config.execution.retry_on_failure:
                time.sleep(self.config.execution.retry_delay)
        
        # Return last failed response
        return LLMResponse(
            text="",
            model=provider.model_name,
            provider=provider.provider_name,
            success=False,
            error=f"Failed after {self.config.execution.max_retries + 1} attempts: {last_error}",
        )
    
    def _evaluate_response(
        self,
        test_case: TestCase,
        model_config: ModelConfig,
        response: LLMResponse,
        prompt: str,
        run_number: int = 1,
    ) -> "TestResult":
        """Evaluate LLM response against expected answer."""
        
        # Extract answer from response
        extracted = self._extract_answer(response.text)
        
        # Compare with expected
        is_correct = self._compare_answers(extracted, test_case.expected_answer)
        
        return TestResult(
            # Identifiers
            question_id=test_case.question_id,
            passage_id=test_case.passage_id,
            format=test_case.format,
            model_name=model_config.name,
            provider=model_config.provider,
            run_number=run_number,
            
            # Question/Answer
            question_text=test_case.question_text,
            expected_answer=test_case.expected_answer,
            extracted_answer=extracted,
            raw_response=response.text,
            
            # Evaluation
            is_correct=is_correct,
            
            # Metadata
            success=response.success,
            error=response.error,
            duration_seconds=response.duration_seconds,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            timestamp=datetime.now().isoformat(),
            
            # Optional storage
            prompt=prompt if self.config.output.save_prompts else None,
            system_prompt=self.system_prompt if self.config.output.save_prompts else None,
        )
    
    def _extract_answer(self, response_text: str) -> str:
        """Extract answer from LLM response."""
        if not response_text:
            return ""
        
        # Try JSON extraction first
        try:
            json_match = re.search(r'\{[^{}]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group(0))
                for key in ['answer', 'result', 'value']:
                    if key in data:
                        return str(data[key])
                # Single key fallback
                if len(data) == 1:
                    return str(list(data.values())[0])
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # Plain text fallback
        text = response_text.strip()
        text = re.sub(r'^(the\s+)?answer\s*(is)?:?\s*', '', text, flags=re.IGNORECASE)
        return text.strip()
    
    def _compare_answers(self, extracted: str, expected: str) -> bool:
        """Compare extracted answer to expected answer."""
        if not extracted or not expected:
            return False
        
        # Normalize both
        def normalize(s: str) -> str:
            s = s.strip().lower()
            # Remove common punctuation
            s = re.sub(r'[.,;:\'"!?]', '', s)
            # Collapse whitespace
            s = re.sub(r'\s+', ' ', s)
            return s
        
        e_norm = normalize(extracted)
        x_norm = normalize(expected)
        
        # Exact match
        if e_norm == x_norm:
            return True
        
        # Numeric comparison
        try:
            e_num = float(e_norm)
            x_num = float(x_norm)
            # Allow small tolerance for floating point
            return abs(e_num - x_num) < 0.01
        except ValueError:
            pass
        
        return False
    
    def _generate_summary(self, all_results: Dict[str, List["TestResult"]]) -> Dict[str, Any]:
        """Generate summary statistics."""
        runs_per_question = self.config.execution.runs_per_question
        
        summary = {
            "run_id": self.config.output.run_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
            "timestamp": datetime.now().isoformat(),
            "runs_per_question": runs_per_question,
            "config": {
                "formats": self.config.filters.formats,
                "verified_only": self.config.filters.verified_only,
                "num_measures": self.config.filters.num_measures,
                "question_types": self.config.filters.question_types,
            },
            "models": {},
            "totals": {
                "test_cases": 0,
                "correct": 0,
                "failed": 0,
            },
        }
        
        for model_name, results in all_results.items():
            correct = sum(1 for r in results if r.is_correct)
            failed = sum(1 for r in results if not r.success)
            total = len(results)
            
            # Per-run breakdown
            by_run = {}
            for r in results:
                if r.run_number not in by_run:
                    by_run[r.run_number] = {"total": 0, "correct": 0}
                by_run[r.run_number]["total"] += 1
                if r.is_correct:
                    by_run[r.run_number]["correct"] += 1
            
            # Consistency analysis
            by_question = {}
            for r in results:
                key = (r.question_id, r.format)
                if key not in by_question:
                    by_question[key] = []
                by_question[key].append(r.is_correct)
            
            consistent_correct = sum(1 for v in by_question.values() if all(v))
            consistent_wrong = sum(1 for v in by_question.values() if not any(v))
            inconsistent = sum(1 for v in by_question.values() if any(v) and not all(v))
            
            summary["models"][model_name] = {
                "total": total,
                "correct": correct,
                "failed": failed,
                "accuracy": correct / total if total > 0 else 0,
                "by_run": {
                    f"run_{k}": {"total": v["total"], "correct": v["correct"],
                                "accuracy": v["correct"] / v["total"] if v["total"] > 0 else 0}
                    for k, v in sorted(by_run.items())
                },
                "consistency": {
                    "unique_questions": len(by_question),
                    "consistent_correct": consistent_correct,
                    "consistent_wrong": consistent_wrong,
                    "inconsistent": inconsistent,
                },
            }
            
            summary["totals"]["test_cases"] += total
            summary["totals"]["correct"] += correct
            summary["totals"]["failed"] += failed
        
        return summary

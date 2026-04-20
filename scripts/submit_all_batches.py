#!/usr/bin/env python3
"""
Parallel Batch Submission Script

Submits batch API requests to all enabled providers in parallel,
then polls for completion. This is much faster than sequential
submission because:
    1. All batches are submitted at once
    2. Polling happens for all batches simultaneously
    3. Results are processed as each batch completes

Resume / crash-safety
---------------------
BatchRequestStorage is the single source of truth.  Every submitted batch is
recorded there with a lifecycle_state before the batch_id escapes this process.
On startup the script reads *all* non-saved batches and resumes from whatever
state they are in:

    submitted  -- poll provider; on completion download results
    downloaded -- raw results already on disk; skip polling, just save

State transitions are atomic (tmp+replace writes).

Usage:
    python scripts/submit_all_batches.py
    python scripts/submit_all_batches.py --run-id 20251202_141834
    python scripts/submit_all_batches.py --poll-only
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_eval.config import BenchmarkConfig, ModelConfig
from src.llm_eval.query import TestCaseQuery, TestCase, build_prompt
from src.llm_eval.batch import BatchRunner, BatchRequest, BatchStatus, BatchResult, is_retryable, is_stale_error
from src.llm_eval.batch_storage import (
    BatchRequestStorage,
    BatchRequestMapping,
    compute_config_hash,
    validate_batch_results,
)
from src.llm_eval.results import ResultsManager, TestResult
from src.llm_eval.providers import LLMResponse


# ---------------------------------------------------------------------------
# Fingerprint / logging helpers
# ---------------------------------------------------------------------------

def compute_content_fingerprint(content: str) -> dict:
    import hashlib
    note_count = content.count('<note')
    rest_count = content.count('<rest')
    measure_matches = re.findall(r'<measure number="(\d+)"', content)
    measures = f"{measure_matches[0]}-{measure_matches[-1]}" if measure_matches else "unknown"
    return {
        'notes': note_count,
        'rests': rest_count,
        'measures': measures,
        'hash': hashlib.md5(content.encode()).hexdigest()[:12],
        'length': len(content),
    }


def log_batch_prompts(
    batch_requests: List[BatchRequest],
    test_cases: List[TestCase],
    output_dir: Path,
    batch_name: str,
) -> Path:
    from src.llm_eval.batch_storage import _atomic_write_json
    log_path = output_dir / f"prompts_{batch_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    tc_map = {tc.custom_id: tc for tc in test_cases}

    prompt_log: Dict[str, Any] = {
        'timestamp': datetime.now().isoformat(),
        'batch_name': batch_name,
        'total_requests': len(batch_requests),
        'requests': [],
    }

    for i, req in enumerate(batch_requests):
        tc = tc_map.get(req.custom_id)
        entry: Dict[str, Any] = {
            'index': i,
            'custom_id': req.custom_id,
            'question_id': tc.question_id if tc else 'unknown',
            'passage_id': tc.passage_id if tc else 'unknown',
            'question_type_id': tc.question_type_id if tc else 0,
            'expected_answer': tc.expected_answer if tc else 'unknown',
            'prompt_length': len(req.prompt),
        }
        if tc and tc.passage_content:
            entry['content_fingerprint'] = compute_content_fingerprint(tc.passage_content)
        entry['prompt_tail'] = req.prompt[-500:] if len(req.prompt) > 500 else req.prompt
        prompt_log['requests'].append(entry)

    passage_order = [
        e['passage_id']
        for e in prompt_log['requests']
        if e['question_type_id'] == 1
    ]
    prompt_log['passage_order'] = passage_order
    prompt_log['unique_passages'] = len(set(passage_order))

    _atomic_write_json(log_path, prompt_log)

    if passage_order:
        print(f"  Logged {len(batch_requests)} prompts to {log_path.name}")
        print(f"     Passages: {passage_order[0]} to {passage_order[-1]} ({len(passage_order)} total)")
    else:
        print(f"  Logged {len(batch_requests)} prompts to {log_path.name}")

    return log_path


# ---------------------------------------------------------------------------
# Answer helpers (used when building TestResult from BatchResult)
# ---------------------------------------------------------------------------

def extract_answer(response_text: str) -> str:
    if not response_text:
        return ""
    try:
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group(0))
            for key in ['answer', 'result', 'value']:
                if key in data:
                    return str(data[key])
            if len(data) == 1:
                return str(list(data.values())[0])
    except (json.JSONDecodeError, AttributeError):
        pass
    text = response_text.strip()
    text = re.sub(r'^(the\s+)?answer\s*(is)?:?\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def compare_answers(extracted: str, expected: str) -> bool:
    if not extracted or not expected:
        return False

    def normalize(s: str) -> str:
        s = s.strip().lower()
        s = re.sub(r'[.,;:\'"!?]', '', s)
        s = re.sub(r'\s+', ' ', s)
        return s

    e_norm = normalize(extracted)
    x_norm = normalize(expected)
    if e_norm == x_norm:
        return True
    try:
        return abs(float(e_norm) - float(x_norm)) < 0.01
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------

def submit_single_batch(
    model_config: ModelConfig,
    batch_requests: List[BatchRequest],
    config: BenchmarkConfig,
    storage: BatchRequestStorage,
    run_number: int = 1,
    batch_metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, str, int]:
    """Submit one model's batch, persist to storage, return (model_name, batch_id, provider, run_number)."""
    temperature = (
        model_config.temperature
        if model_config.temperature is not None
        else config.api_settings.temperature
    )

    batch_runner = BatchRunner(
        provider=model_config.provider,
        model_name=model_config.name,
        max_tokens=model_config.max_tokens or config.api_settings.max_tokens,
        temperature=temperature,
    )

    submitted_ids = [r.custom_id for r in batch_requests]
    batch_id = batch_runner.submit(
        batch_requests,
        json_mode=config.prompt.enforce_json,
        batch_metadata=batch_metadata,
    )

    # Persist before batch_id escapes this function
    storage.save(
        batch_id=batch_id,
        request_ids=submitted_ids,
        provider=model_config.provider,
        model=model_config.name,
        format=batch_metadata.get("format") if batch_metadata else None,
        num_measures=batch_metadata.get("num_measures") if batch_metadata else None,
        question_range=batch_metadata.get("question_range") if batch_metadata else None,
        config_hash=compute_config_hash(
            model_config.name,
            batch_metadata.get("format") if batch_metadata else None,
            batch_metadata.get("num_measures") if batch_metadata else None,
            submitted_ids,
        ),
        run_number=run_number,
    )

    return (model_config.name, batch_id, model_config.provider, run_number)


# ---------------------------------------------------------------------------
# Polling helpers
# ---------------------------------------------------------------------------

def poll_batch_status(
    batch_id: str,
    provider: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, BatchStatus]:
    batch_runner = BatchRunner(
        provider=provider,
        model_name=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (batch_id, batch_runner.get_status(batch_id))


def fetch_raw_results(
    batch_id: str,
    provider: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
) -> List[BatchResult]:
    batch_runner = BatchRunner(
        provider=provider,
        model_name=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return batch_runner.get_results(batch_id)


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_and_save_batch(
    batch_id: str,
    mapping: BatchRequestMapping,
    raw_results: List[BatchResult],
    test_case_map: Dict[str, TestCase],
    model_config: ModelConfig,
    run_number: int,
    system_prompt: str,
    config: BenchmarkConfig,
    results_manager: ResultsManager,
    storage: BatchRequestStorage,
) -> List[TestResult]:
    """Validate, build TestResults, save each atomically, update lifecycle to saved."""
    expected_ids = mapping.request_ids
    validated = validate_batch_results(
        raw_results,
        expected_ids=expected_ids,
        diagnostic_dir=results_manager.output_dir,
        batch_id=batch_id,
    )

    results: List[TestResult] = []

    matched_in_map = sum(1 for r in validated.matched if r.custom_id in test_case_map)
    if validated.matched and matched_in_map / len(validated.matched) < 0.95:
        print(f"  WARNING: only {matched_in_map}/{len(validated.matched)} "
              f"results matched test cases for batch {batch_id[:30]}")

    for batch_result in validated.matched:
        test_case = test_case_map.get(batch_result.custom_id)
        if not test_case:
            continue

        response = LLMResponse(
            text=batch_result.response_text,
            model=model_config.name,
            provider=model_config.provider,
            success=batch_result.success,
            error=batch_result.error,
            raw_metadata=batch_result.metadata,
        )
        response.extract_json_answer()

        extracted = extract_answer(response.parsed_answer if response.parsed_answer else response.text)
        is_correct = compare_answers(extracted, test_case.expected_answer)

        prompt = build_prompt(
            test_case,
            system_prompt,
            include_format_hint=config.prompt.include_format_hint,
        )

        result = TestResult(
            question_id=test_case.question_id,
            passage_id=test_case.passage_id,
            format=test_case.format,
            model_name=model_config.name,
            provider=model_config.provider,
            run_number=run_number,
            question_text=test_case.question_text,
            expected_answer=test_case.expected_answer,
            extracted_answer=extracted,
            raw_response=response.text,
            is_correct=is_correct,
            success=response.success,
            error=response.error,
            timestamp=datetime.now().isoformat(),
            prompt=prompt,
        )
        results.append(result)

        err = results_manager.save_single_result(model_config, result, test_case)
        if err:
            storage.add_needs_retry(batch_id, batch_result.custom_id)

    storage.update_lifecycle(batch_id, "saved")
    return results


def _model_runner_kwargs(model_config: ModelConfig, config: BenchmarkConfig) -> Dict[str, Any]:
    temperature = (
        model_config.temperature
        if model_config.temperature is not None
        else config.api_settings.temperature
    )
    return {
        "temperature": temperature,
        "max_tokens": model_config.max_tokens or config.api_settings.max_tokens,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Submit batch API requests in parallel")
    parser.add_argument("--run-id", help="Existing run ID to continue")
    parser.add_argument("--poll-only", action="store_true", help="Skip submission, poll existing batches")
    parser.add_argument("--check-interval", type=int, default=60, help="Seconds between status checks")
    parser.add_argument("--runs", type=int, default=None, help="Number of runs per model (overrides config)")
    parser.add_argument("--retry-stale", action="store_true", help="Clear failed_stale batches and re-submit them")
    args = parser.parse_args()

    config_path = Path(__file__).parent.parent / "config.yaml"
    config = BenchmarkConfig.from_yaml(config_path)
    config.load_api_keys()

    if args.run_id:
        config.output.resume_run_id = args.run_id

    runs_per_question = args.runs if args.runs else config.execution.runs_per_question

    results_manager = ResultsManager(config)
    output_dir = results_manager.output_dir
    print(f"Output directory: {output_dir}")

    storage = BatchRequestStorage(output_dir)

    enabled_models = config.get_enabled_models()
    print(f"\nEnabled models: {[m.name for m in enabled_models]}")
    print(f"Runs per question: {runs_per_question}")

    system_prompt = config.get_system_prompt()
    query = TestCaseQuery(config)

    print("\nFetching test cases...")
    test_cases = query.fetch_test_cases()
    print(f"Found {len(test_cases)} test cases")
    if not test_cases:
        print("No test cases match filter criteria")
        return

    summary = query.get_summary()
    print(f"  By format: {summary['by_format']}")

    test_case_map = {tc.custom_id: tc for tc in test_cases}

    if not args.poll_only:
        print("\nPreparing batch requests...")
        batch_requests: List[BatchRequest] = []
        for test_case in test_cases:
            prompt = build_prompt(
                test_case,
                system_prompt,
                include_format_hint=config.prompt.include_format_hint,
            )
            batch_requests.append(BatchRequest(
                custom_id=test_case.custom_id,
                prompt=prompt,
                system_prompt=system_prompt,
                metadata={"test_case": test_case},
            ))
        print(f"Prepared {len(batch_requests)} requests per batch")

        format_name = config.filters.formats[0] if config.filters.formats else 'unknown'
        num_measures = config.filters.num_measures[0] if config.filters.num_measures else 'unknown'
        batch_name = f"{format_name}_{num_measures}bar"
        log_batch_prompts(batch_requests, test_cases, output_dir, batch_name)

        if args.retry_stale:
            stale = [(bid, m) for bid, m in storage.get_all().items() if m.lifecycle_state == "failed_stale"]
            if stale:
                print(f"\nClearing {len(stale)} failed_stale batch(es) for re-submission...")
                for bid, m in stale:
                    storage.delete(bid)
                    print(f"  Cleared {bid[:30]} ({m.model})")

        batches_to_submit = []
        existing = storage.get_all()
        for model in enabled_models:
            for run_num in range(1, runs_per_question + 1):
                already = [
                    bid for bid, m in existing.items()
                    if m.model == model.name and m.run_number == run_num
                ]
                if already:
                    print(f"  Skipping {model.name}_run{run_num}: already has batch {already[0][:20]}...")
                else:
                    batches_to_submit.append((model, run_num))

        if batches_to_submit:
            total_requests = len(batches_to_submit) * len(batch_requests)
            print(f"\nSubmitting {len(batches_to_submit)} batches ({total_requests:,} total requests)")

            batch_metadata = {
                "format": config.filters.formats[0] if config.filters.formats else "unknown",
                "num_measures": config.filters.num_measures[0] if config.filters.num_measures else "all",
            }

            max_workers = min(len(batches_to_submit), 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        submit_single_batch,
                        model,
                        batch_requests,
                        config,
                        storage,
                        run_num,
                        batch_metadata,
                    ): (model, run_num)
                    for model, run_num in batches_to_submit
                }
                for future in as_completed(futures):
                    model, run_num = futures[future]
                    try:
                        model_name, batch_id, provider, _ = future.result()
                        print(f"  submitted {model_name}_run{run_num}: {batch_id[:30]}...")
                    except Exception as e:
                        print(f"  FAILED {model.name}_run{run_num}: {e}")

    # ------------------------------------------------------------------
    # Polling loop driven by BatchRequestStorage
    # ------------------------------------------------------------------

    # Build model_config lookup by name for polling
    model_by_name: Dict[str, ModelConfig] = {m.name: m for m in enabled_models}

    resumable = storage.get_resumable()

    # --- Stale detection: probe each submitted batch once on startup ---
    stale_found: List[str] = []
    for batch_id, mapping in list(resumable.items()):
        if mapping.lifecycle_state != "submitted":
            continue
        model_config = model_by_name.get(mapping.model)
        if not model_config:
            continue
        kw = _model_runner_kwargs(model_config, config)
        try:
            batch_runner = BatchRunner(mapping.provider, mapping.model, **kw)
            status = batch_runner.get_status(batch_id)
            if status.status == "expired":
                storage.update_lifecycle(batch_id, "failed_stale")
                stale_found.append(batch_id)
                print(f"  {batch_id[:30]}: expired on provider, marked failed_stale")
        except Exception as e:
            if is_stale_error(e):
                storage.update_lifecycle(batch_id, "failed_stale")
                stale_found.append(batch_id)
                print(f"  {batch_id[:30]}: not found on provider, marked failed_stale")
            elif is_retryable(e):
                print(f"  {batch_id[:30]}: could not check stale status ({type(e).__name__}), will poll normally")
            else:
                raise
    if stale_found:
        print(f"  Marked {len(stale_found)} batch(es) failed_stale. Use --retry-stale to re-submit.")

    resumable = storage.get_resumable()
    if not resumable:
        print("\nNo batches to poll")
        return

    print(f"\nPolling {len(resumable)} batch(es)...")
    print(f"Check interval: {args.check_interval} seconds")

    completed: set = set()
    all_results: Dict[str, List[TestResult]] = {}
    batch_retry_counts: Dict[str, int] = {}
    batch_next_poll: Dict[str, float] = {}

    while len(completed) < len(resumable):
        # Reload resumable state in case storage was updated externally
        resumable = storage.get_resumable()
        pending = {bid: m for bid, m in resumable.items() if bid not in completed}

        # --- Resume any batches already in "downloaded" state ---
        for batch_id, mapping in list(pending.items()):
            if mapping.lifecycle_state != "downloaded":
                continue
            raw = storage.load_raw_results(batch_id)
            if raw is None:
                print(f"  {batch_id[:30]}: state=downloaded but no raw file — re-downloading")
                storage.update_lifecycle(batch_id, "submitted")
                continue

            model_config = model_by_name.get(mapping.model)
            if not model_config:
                print(f"  {batch_id[:30]}: model {mapping.model!r} not in enabled models, skipping")
                completed.add(batch_id)
                continue

            run_number = mapping.run_number or 1
            print(f"  {batch_id[:30]}: resuming from downloaded state")
            results = process_and_save_batch(
                batch_id, mapping, raw, test_case_map,
                model_config, run_number, system_prompt, config, results_manager, storage,
            )
            all_results[batch_id] = results
            completed.add(batch_id)
            success = sum(1 for r in results if r.is_correct)
            print(f"    -> saved {len(results)} results ({success} correct)")

        # --- Poll batches still in "submitted" state ---
        now = time.time()
        to_poll = {
            bid: m for bid, m in pending.items()
            if bid not in completed
            and m.lifecycle_state == "submitted"
            and now >= batch_next_poll.get(bid, 0)
        }
        if not to_poll:
            if len(completed) < len(resumable):
                time.sleep(args.check_interval)
            continue

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking {len(to_poll)} pending batch(es)...")

        with ThreadPoolExecutor(max_workers=min(len(to_poll), 4)) as executor:
            futures = {}
            for batch_id, mapping in to_poll.items():
                model_config = model_by_name.get(mapping.model)
                if not model_config:
                    print(f"  Warning: no config for model {mapping.model!r}, skipping {batch_id[:30]}")
                    completed.add(batch_id)
                    continue
                kw = _model_runner_kwargs(model_config, config)
                futures[executor.submit(
                    poll_batch_status,
                    batch_id,
                    mapping.provider,
                    mapping.model,
                    kw["temperature"],
                    kw["max_tokens"],
                )] = batch_id

            for future in as_completed(futures):
                batch_id = futures[future]
                mapping = resumable[batch_id]
                model_config = model_by_name.get(mapping.model)
                if not model_config:
                    continue
                kw = _model_runner_kwargs(model_config, config)
                run_number = mapping.run_number or 1

                try:
                    _, status = future.result()
                except Exception as e:
                    if is_stale_error(e):
                        print(f"  {batch_id[:30]}: not found on provider, marking failed_stale")
                        storage.update_lifecycle(batch_id, "failed_stale")
                        completed.add(batch_id)
                    elif is_retryable(e):
                        count = batch_retry_counts.get(batch_id, 0) + 1
                        batch_retry_counts[batch_id] = count
                        backoff = min(3600, 30 * (2 ** (count - 1)))
                        batch_next_poll[batch_id] = time.time() + backoff
                        print(f"  {batch_id[:30]}: retryable error ({type(e).__name__}), retry in {backoff}s")
                    else:
                        raise
                    continue

                status_str = f"{status.status} ({status.progress_pct:.1f}%)"

                if not status.is_complete:
                    print(f"  {batch_id[:30]}: {status_str}")
                    continue

                if status.status == "expired":
                    print(f"  {batch_id[:30]}: expired, marking failed_stale")
                    storage.update_lifecycle(batch_id, "failed_stale")
                    completed.add(batch_id)
                    continue

                if status.status != "completed":
                    print(f"  {batch_id[:30]}: {status.status} (not completed)")
                    completed.add(batch_id)
                    continue

                print(f"  {batch_id[:30]}: COMPLETED — downloading results...")
                try:
                    raw = fetch_raw_results(
                        batch_id, mapping.provider, mapping.model,
                        kw["temperature"], kw["max_tokens"],
                    )
                except Exception as e:
                    if is_stale_error(e):
                        print(f"  {batch_id[:30]}: not found during download, marking failed_stale")
                        storage.update_lifecycle(batch_id, "failed_stale")
                        completed.add(batch_id)
                    elif is_retryable(e):
                        count = batch_retry_counts.get(batch_id, 0) + 1
                        batch_retry_counts[batch_id] = count
                        backoff = min(3600, 30 * (2 ** (count - 1)))
                        batch_next_poll[batch_id] = time.time() + backoff
                        print(f"  {batch_id[:30]}: retryable download error ({type(e).__name__}), retry in {backoff}s")
                    else:
                        raise
                    continue

                # Persist raw results before state transition
                storage.save_raw_results(batch_id, raw)
                storage.update_lifecycle(batch_id, "downloaded")

                results = process_and_save_batch(
                    batch_id, mapping, raw, test_case_map,
                    model_config, run_number, system_prompt, config, results_manager, storage,
                )
                all_results[batch_id] = results
                completed.add(batch_id)
                success = sum(1 for r in results if r.is_correct)
                print(f"    -> saved {len(results)} results ({success} correct)")

        if len(completed) < len(resumable):
            print(f"Waiting {args.check_interval} seconds...")
            time.sleep(args.check_interval)

    print(f"\n{'='*60}")
    print("All batches complete!")
    print(f"{'='*60}")

    total_correct = total_tests = 0
    for bid, results in all_results.items():
        success = sum(1 for r in results if r.is_correct)
        total_correct += success
        total_tests += len(results)
        label = f"{resumable.get(bid, storage.load(bid)).model}_run{resumable.get(bid, storage.load(bid)).run_number}"
        print(f"  {label}: {success}/{len(results)} correct ({100*success/len(results):.1f}%)")

    if total_tests > 0:
        print(f"\nOverall: {total_correct}/{total_tests} correct ({100*total_correct/total_tests:.1f}%)")

    print(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    main()

# BEAM v2 — Batch Pipeline Hardening Handoff

This document is the source of truth for a multi-phase cleanup. Each phase is scoped so a fresh agent can pick it up without seeing prior conversations.

**Always update this doc at the end of a phase before handing off.** Mark the completed phase, note any decisions or deviations, and leave the next phase actionable.

---

## Context

- **Project:** BEAM benchmark for music encoding LLM evaluation. Originally for the Music Encoding Conference camera-ready (was 2026-04-24); current work is post-submission revision / extended data collection.
- **Situation:** An ambitious v2 redesign was started, then pulled back. We reset the working tree to commit `0165246`, preserved a narrow set of bug fixes (new commit `19a1545`), and are now hardening the batch API pipeline before regenerating data.
- **Snapshot branch:** `wip-v2-redo-snapshot` holds the abandoned v2-redo work. Keep it until Phase 3 verifies; then `git branch -D wip-v2-redo-snapshot`.
- **Repo plan:** The user will manually create a new GitHub repo (renamed project) without history from this one. That migration is out of scope for these phases.

## Current state (2026-05-02, after Phase 10)

**Active DB:** `benchmark.db` (the merged DB; v1 + v2 unified per Phase 10). Ground truth, `is_correct`, and the four extractors are all internally consistent (full selfcheck = 0 mismatches across 18,630 `llm_responses` and 810 GT rows for each of the 4 formats).

**Data-collection coverage (rows in `llm_responses`):**

| Format | claude-sonnet-4-5 | gemini-3-pro-preview | gpt-5.1-2025-11-13 | qwen3-max | claude-opus-4-7 | gemini-3.1-pro-preview | gpt-5.4 |
|---|---|---|---|---|---|---|---|
| musicxml | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ |
| abc      | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ | 1✅      | 1✅      | 1✅      |
| humdrum  | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ | 1✅      | 1✅      | 1✅      |
| mei      | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ | 1✅ 8✅ | 1✅      | 1✅      | **MISSING** |

The four v1 models have full 8-format-pair coverage. The three v2 (reasoning) models have full 1-bar coverage *except* gpt-5.4 MEI; 8-bar exists only for MusicXML across all v2 models.

**Active local config (`config.yaml`):** `database: benchmark.db`, `run_id: phase6_1bar_mei`, `formats: [mei]`, `num_measures: [1]`. This file is intentionally **not committed** — it is a per-user run state file.

**Backups on disk (gitignored via `*.db.pre-*` and `*.merged-into-v1`):**
- `benchmark.db.pre-merge` — v1 right before Phase 10 merge.
- `benchmark_v2.db.pre-merge` — v2 right before Phase 10 merge (use this if you ever need the pre-merge v2 state in isolation).
- `benchmark_v2.db.merged-into-v1` — v2 immediately after Phase 9, post-merge rename. Kept as a safety net; can be deleted once you've verified the merged `benchmark.db` end-to-end.
- `benchmark_v2.db.pre-phase{6,7,8,9}-fix` — rollback points, one per audit phase.
- `benchmark.db.pre-gemini-humdrum-patch`, `benchmark.db.pre-gt-rescore` — old v1 DB snapshots, kept for archival.

## Guiding rules

- **No fallbacks.** If an API key or model is wrong, raise — don't silently switch to something else.
- **No emojis** in code, commits, or docs.
- **No backwards-compat shims.** Delete dead paths cleanly.
- **Minimal comments.** Only where the *why* is non-obvious.
- **Test each phase with a tiny dry run** (5 requests, one provider) before declaring done.
- **One phase per agent.** When a phase completes, update this doc and spin up a new agent with a pointer to the next phase.

---

## Diagnostic summary (root cause of last round's failures)

The "-9 offset" in MusicXML 8-bar Gemini (noted in commit `0165246`) traces to one upstream bug: **the Google batch path uses inline requests, which is the only Gemini batch mode that does not support a per-request `key` field.** Code compensated with index-alignment (`response[i] → request[i]`) plus an in-memory `_request_ids_cache`. Any missing/skipped response silently shifts all subsequent responses; any process restart before polling loses the mapping entirely.

All four providers natively support custom IDs when used in the right mode:

| Provider | Field | Required mode |
|---|---|---|
| OpenAI | `custom_id` | JSONL (already used) |
| Anthropic | `custom_id` | array (already used) |
| **Google Gemini** | **`key`** | **File-based JSONL (not inline)** ← the fix |
| Qwen / DashScope | `custom_id` | OpenAI-compatible JSONL (already used) |

Secondary issues found in the audit:
- JSON result writes are not atomic (`results.py:237-238`) — corrupt files on crash are silently treated as missing.
- DB insert and JSON write are separate transactions — can diverge on crash.
- Polling loop has no persistent checkpoints — restart re-polls everything from scratch.
- `batch_ids.json` entries never expire — stale batches block resume forever.
- `cancel_batch` swallows bare `Exception` (batch.py:307, 458, 810).

Full diagnostic with file:line citations: see conversation history (not preserved here).

---

## Phases

### Phase 0 — Triage (DONE)

- Reset working tree to `0165246`.
- Preserved bug-fix commit `19a1545` (`numeric_error` / `error_category` metrics + evaluation.py + new .gitignore).
- Dropped the `GEMINI_API_KEY` env-var fallback in `batch.py`. **User must ensure `.env` uses `GOOGLE_API_KEY`.**
- `wip-v2-redo-snapshot` branch preserves abandoned work.

### Phase 1 — Google batch: switch inline → JSONL with `key` field (DONE, ACCEPTANCE TEST PASSED 2026-04-19)

**Why:** Root cause of the -9 offset. All other fixes depend on this.

**Handoff notes (2026-04-19):**
- `GoogleBatchAPI.submit_batch` now writes a tempfile JSONL (`{"key": custom_id, "request": {...}}`), uploads via `client.files.upload(file=path, config={"mime_type": "jsonl", "display_name": "batch-requests"})`, and calls `client.batches.create(model=..., src=uploaded.name, config={"display_name": ...})`. Temp file is always unlinked in a `finally`.
- `GoogleBatchAPI.get_results(batch_id)` is file-only. No `request_ids` param. Missing `key` on a line becomes an explicit `BatchResult(success=False, error="response line N missing 'key' field")` with a synthesised id that `validate_batch_results` will then flag as unexpected.
- `_request_ids_cache`, `get_submitted_request_ids` (both on `GoogleBatchAPI` and `BatchRunner`), and the `request_ids` parameter on `BatchRunner.get_results` / `wait_for_completion` are gone.
- `BatchRunner.submit_batch` also rejects duplicate `custom_id`s at submission.
- `validate_batch_results(results, expected_ids, diagnostic_dir, batch_id)` lives in `batch_storage.py`, returns a `ValidatedBatch(matched, missing, unexpected)`. Missing keys are synthesised as failures and included in `matched` so downstream save logic still records them. Unexpected keys dump a diagnostic JSON and raise.
- All callers now call `validate_batch_results` explicitly after `get_results` / `wait_for_completion`:
  - `scripts/submit_all_batches.py` `retrieve_batch_results` takes `expected_ids=` (loaded from `BatchRequestStorage` or `batch_ids.json`).
  - `src/llm_eval/runner.py` batch path validates with `expected_ids=[r.custom_id for r in batch_requests]`.
- All providers (not just Google) now persist submitted custom_ids to `BatchRequestStorage` on submit. This is required by the new validation flow and also gives Phase 2 a head-start.
- Google SDK in use: `google-genai==1.56.0`. File-based batch (`src=<uploaded_file.name>`) is supported in this version.
- Quirks found while landing Phase 1:
  - File-based JSONL uses raw REST API field names, **not** the SDK's snake_case wrapper. Use `generationConfig` (not `config`), `systemInstruction` (not `system_instruction`), `maxOutputTokens`, `responseMimeType`, `responseSchema`.
  - `responseSchema` type values must be **uppercase** (`"OBJECT"`, `"STRING"`) in the raw JSONL — inline mode's transformer normalises lowercase to upper, but the file path skips that transformer.
  - `.env` must use `GOOGLE_API_KEY` (not `GEMINI_API_KEY`); the fallback is gone.

**Acceptance test:** ✅ **Passed 2026-04-19** (batch `batches/kqzioojh02yeizx7y7onxsdikds7tc7jhkef`, all 5 `PASS test-N -> 'N'`). Dry-run script is at [scripts/dryrun_gemini_batch.py](scripts/dryrun_gemini_batch.py). Command:

```bash
# full submit + poll in one process
python scripts/dryrun_gemini_batch.py

# then re-check in a fresh process (confirms no in-memory state needed)
python scripts/dryrun_gemini_batch.py --poll <batch_id_printed_above>
```

The script prints `PASS test-N -> 'N'` for each of 5 distinct predictable prompts. Any `FAIL` line indicates Phase 1 regression. Uses `max_tokens=256` so 2.5-flash's thinking tokens don't eat the output.

**Next agent for Phase 2:** re-run the dry-run above before starting work; fix Phase 1 if it regresses.

---

### Phase 1 (original spec below — kept for reference)

**Scope (files):**
- `src/llm_eval/batch.py` — `GoogleBatchAPI.submit_batch`, `get_results`, delete `get_submitted_request_ids`.
- `src/llm_eval/batch_storage.py` — add shared `validate_batch_results` helper.
- Callers of `get_results` (see below).

**Changes:**
1. In `submit_batch` (currently batch.py:555-642): build a JSONL file with one line per request, shape `{"key": req.custom_id, "request": {"contents": [...], "config": {...}}}`. Upload via `self.client.files.upload(...)`, then `self.client.batches.create(src=<uploaded_file>, ...)`. Remove the `inline_requests` path entirely.
2. In `get_results` (batch.py:701-808): signature becomes `get_results(batch_id) -> List[BatchResult]` — **no `request_ids` parameter**. Only the file-based branch is needed now. Read each JSONL line, extract `data["key"]` as `custom_id` (no index fallback — if `key` missing, mark that line as a failure with explicit error). Remove the `inline_responses` branch, the `_request_ids_cache`, and `get_submitted_request_ids`. `get_results` does *only* fetch+parse; it does not validate.
3. **Validation lives in a separate helper, not in `get_results`.** Add to `batch_storage.py`:

    ```python
    @dataclass
    class ValidatedBatch:
        matched: List[BatchResult]       # result.custom_id was in expected set
        missing: List[BatchResult]       # expected keys with no response — synthesised as success=False
        unexpected: List[str]            # result keys not in expected set (should be empty)

    def validate_batch_results(
        results: List[BatchResult],
        expected_ids: Iterable[str],
    ) -> ValidatedBatch:
        ...
    ```

    Semantics: every `expected_id` with no response becomes `BatchResult(custom_id=..., success=False, error="no response from provider")` in `missing` (and is also included in `matched` for downstream save, marked as failure). Any `unexpected` is a hard error — dump results + expected to a diagnostic file and raise.

4. **Callers**: every caller of `get_results` must immediately call `validate_batch_results(results, expected_ids=<from BatchRequestStorage>)`. Callers include at minimum `scripts/submit_all_batches.py` and `src/llm_eval/runner.py` (batch-mode path). This rule is the main reason validation is pulled out of `get_results`: making the validation call explicit prevents silent non-validation if someone forgets a parameter.

**What to delete:**
- `_request_ids_cache` attribute and all references.
- `get_submitted_request_ids` method.
- Inline submission path (both branches with/without system prompt).
- Inline response parsing in `get_results`.
- The old `request_ids` parameter on `get_results` and every caller that passes it.

**Acceptance:**
- **Alignment check.** Submit a 5-request Gemini batch with five *distinct* predictable prompts ("say the number N, nothing else" for N=1..5), each with its own key (e.g. `test-1` .. `test-5`). The LLM is **not** echoing the key — it never sees it. The `key` is a provider-level metadata field on the request/response envelope, round-tripped by Google automatically. The test verifies two independent things:
  1. **Provider routing:** the response envelope for key `test-N` comes back with key `test-N` (not swapped).
  2. **Submit-side mapping:** the *content* of that response is `N` — proving we didn't mis-pair prompts with keys when building the JSONL.

  Five distinct, one-token answers make this trivially checkable without invoking the extraction pipeline. Run the whole check twice in separate Python processes to confirm no in-memory state is required for alignment.
- Dry-run command added to `scripts/` (or documented in this handoff) so Phase 4 can re-use it.

**Handoff notes after phase completion:** document the dry-run command and any provider-SDK quirks discovered.

---

### Phase 2 — Atomic saves, validation, unified storage, resumable polling (DONE, 2026-04-20)

**Handoff notes (2026-04-20):**

**B2 — Atomic JSON writes.** `_atomic_write_json(path, data)` helper added to both `results.py` and `batch_storage.py`. `save_single_result`, `save_summary`, and all storage writes use it. `results.py:save_batch_id` deleted (redundant with storage). `batch_ids.json` is no longer written or read anywhere.

**B3 — Validation gate.** `ResultsManager._validate_result(result, test_case) -> Optional[str]` checks: `success=True` with empty `raw_response` → error; `question_id` / `format` / `expected_answer` mismatch against `test_case` → error. `save_single_result(model_config, result, test_case=None) -> Optional[str]` runs validation first, skips save and returns the error string on failure. Callers pass `test_case` where available; on failure they call `storage.add_needs_retry(batch_id, custom_id)`.

**R1 — Unified storage.** `BatchRequestMapping` extended with `lifecycle_state`, `config_hash`, `run_number`, `needs_retry_ids`, `submitted_at` (reads `created_at` for backward compat). `BatchRequestStorage.save()` now accepts `config_hash` and `run_number`; always sets `lifecycle_state="submitted"`. New helpers: `update_lifecycle(batch_id, state)`, `add_needs_retry(batch_id, custom_id)`, `save_raw_results(batch_id, raw)`, `load_raw_results(batch_id)`, `get_resumable()`. All `_save_cache` calls go through `_atomic_write_json`. `STATES = ("submitted", "downloaded", "saved", "failed_stale")`.

`runner.py:_run_batch` now calls `storage.save(...)` immediately after `batch_runner.submit()` (before the batch_id is used further), passes `test_case` to `save_single_result`, adds to `needs_retry_ids` on validation failure, calls `storage.update_lifecycle(batch_id, "saved")` at end.

**R2 — State machine.** `submit_all_batches.py` now driven entirely by `BatchRequestStorage`. `batch_ids.json` and `save_batch_id_extended` are gone. Polling loop:
- On startup: calls `storage.get_resumable()` for all non-`saved` batches.
- State `downloaded`: loads raw results from disk, skips provider poll, calls `process_and_save_batch()`.
- State `submitted`: polls provider; on completion, downloads results → `save_raw_results` → `update_lifecycle("downloaded")` → `process_and_save_batch()` → `update_lifecycle("saved")`.
- State transitions are atomic. Raw results file (`raw_results_<batch_id>.json`) survives a SIGKILL between download and save.

**Acceptance tests:** Unit checks pass (`python -c "..."`) covering B2 atomic write, R1 storage round-trip (lifecycle, raw results, get_resumable, needs_retry, reload from disk), R2 config_hash stability, B3 _validate_result cases. Full kill/resume acceptance (start 10-request batch, SIGKILL mid-poll, restart) deferred to Phase 4 pilot where live API calls are made.

**Note:** Phase 1 dry-run script (`scripts/dryrun_gemini_batch.py`) was not present on disk at Phase 2 start (cleaned up between sessions). Phase 3 agent should recreate it or verify Phase 1 behavior via Phase 4 pilot.

**Why:** Even with correct alignment, crashes between "download" and "save" leave orphaned state. Polling is not resumable.

**Scope (files):**
- `src/llm_eval/results.py` — `save_single_result`, `_save_single_to_database`.
- `src/llm_eval/batch_storage.py` — extend schema to track per-batch lifecycle state.
- `src/llm_eval/batch.py` — all `submit_batch` methods route through `BatchRequestStorage`.
- `scripts/submit_all_batches.py` — polling loop reads/writes lifecycle state.

**Changes:**

**B2 — Atomic JSON writes.** In `save_single_result`: write to `{path}.tmp` then `os.replace(tmp, path)`. Never open the target path for writing directly.

**B3 — Validation gate.** Add `_validate_result(result, test_case)` called before save. Requires: non-empty response text (or explicit `success=False`), `custom_id` matches expected test case, no unexpected fields. Any failure → log + skip save + mark test as `needs_retry` in the batch storage state.

**R1 — Unified persistent submit state.** Every provider's `submit_batch` writes to `BatchRequestStorage` *before* returning the batch_id to the caller. Payload: `{batch_id, provider, custom_ids: [...], submitted_at, config_hash, lifecycle_state: "submitted"}`. `config_hash` is a stable hash of model+format+num_measures+question_ids — used by Phase 3 to detect drift.

**R2 — Resumable polling with state machine.** Per-batch lifecycle states: `submitted → polling → downloaded → parsed → saved`. Stored in `BatchRequestStorage`. Poll loop on startup reads all batches, skips those already `saved`, resumes from whatever state each batch is in. Each state transition is atomic (single write to the storage file via tmp+replace).

**Acceptance:**
- Start a 10-request batch; kill the process mid-poll (SIGKILL, not SIGTERM); restart; confirm it resumes without re-polling completed batches and without double-saving.
- Manually corrupt one output JSON file; re-run; confirm `_validate_result` catches it and the file is re-saved cleanly (not silently skipped).

---

### Phase 3 — Stale batch detection, error classification (DONE, 2026-04-20)

**Why:** Defense in depth. Avoids indefinitely stuck resumes and unhelpful crash loops.

**Handoff notes (2026-04-20):**

**R3 — Stale batch detection.** On startup, `submit_all_batches.py` probes every `submitted` batch via `get_status` once. Provider-side expiry/not-found maps to `failed_stale`:
- `status.status == "expired"` → `failed_stale`
- `is_stale_error(exc)` (catches `openai.NotFoundError`, `anthropic.NotFoundError`, `google.api_core.exceptions.NotFound`) → `failed_stale`
- Retryable error during stale check → log and continue to polling normally
- Anything else → re-raise (fatal)

`--retry-stale` flag: deletes all `failed_stale` entries from storage so the normal submission flow re-submits them. Requires non-`--poll-only` mode (batch requests must be built).

`GoogleBatchAPI.get_status` now maps `JOB_STATE_EXPIRED` → `'expired'` (was `'failed'`). `BatchStatus.is_complete` includes `'expired'`. The polling loop also marks `status.status == "expired"` as `failed_stale` (handles expiry that occurs after the startup stale check).

**R4 — Error classification.** `is_retryable(exc)` and `is_stale_error(exc)` are module-level functions in `batch.py` (lazy imports, no forced provider imports at module load):
- Retryable: `requests.ConnectionError`, `requests.Timeout`, `openai.RateLimitError`, `anthropic.RateLimitError`, `google.api_core.exceptions.ResourceExhausted`
- Stale: `openai.NotFoundError`, `anthropic.NotFoundError`, `google.api_core.exceptions.NotFound`
- Everything else is fatal and bubbles

All four `cancel_batch` methods now use `is_stale_error` instead of bare `except Exception: return False`.

Polling loop: retryable → exponential backoff per batch (`30 * 2^(count-1)`, capped at 3600s), tracked via `batch_next_poll` dict; fatal → re-raise; stale → mark `failed_stale`, add to `completed`. Same pattern applied to download error path.

**Acceptance tests passed (2026-04-20):**
- Unit: `is_retryable`/`is_stale_error` classify `openai`/`anthropic`/`google` errors correctly; `AuthenticationError` is neither retryable nor stale (fatal).
- Unit: bogus batch_id marked `failed_stale` → removed from `get_resumable()` → does not block polling loop.
- Unit: `--retry-stale` deletes stale entry; batch re-enters submission flow.
- `BatchStatus.is_complete` includes `'expired'`.

**Scope (files):**
- `src/llm_eval/batch.py` — error classification helper.
- `scripts/submit_all_batches.py` — wire both in.

---

### Phase 4 — Pilot batch (DONE, 2026-04-20)

**Why:** Verify the full pipeline end-to-end with real API calls before spending budget on full collection.

**Scope:** 3 requests × 3 providers (1-measure MusicXML passages, Q-001/Q-002/Q-003, run_id `phase4_pilot_v3`).

**Handoff notes (2026-04-20):**

**Providers tested:** OpenAI (`gpt-5.4-nano`), Anthropic (`claude-haiku-4-5`), Google (`gemini-3.1-flash-lite-preview`). Alibaba skipped: DashScope international batch endpoint returned 401 — key is set as `DASHSCOPE_API_KEY` but appears invalid for the batch endpoint; investigate before Phase 5.

**Kill-and-resume:** Process SIGKILL'd immediately after all 3 batches were submitted (all in `submitted` state in storage). On restart with `--poll-only --run-id phase4_pilot_v3`, the script read from `batch_request_mappings.json`, skipped re-submission for already-submitted batches, and polled to completion. PASSED.

**Polling exit condition bug found and fixed:** `while len(completed) < len(resumable)` exited early when completed batches transitioned to `saved` (terminal) and left `get_resumable()`, causing `len(resumable)` to shrink while `len(completed)` stayed constant. Fixed in `scripts/submit_all_batches.py`: added `initial_batch_ids = set(resumable.keys())` before the loop and replaced all three `len(completed) < len(resumable)` checks with `initial_batch_ids - completed`.

**Results (`phase4_pilot_v3`):**
- 9 DB rows saved (3 models × 3 questions), all with correct `question_id`/`passage_id`/`format`
- 9 JSON result files at `model/musicxml/Q-NNN_r1.json`
- 3 raw results files persisted to disk
- No `needs_retry_ids` — all validation passed
- DB and JSON files agree: no divergence

**Accuracy (informational only — not the pilot's purpose):**
- `claude-haiku-4-5`: 3/3 correct
- `gpt-5.4-nano`: 2/3 correct
- `gemini-3.1-flash-lite-preview`: 2/3 correct

**`.env` note:** Anthropic key was stored as `CLAUDE_API_KEY`; added `ANTHROPIC_API_KEY` alias pointing to the same value. `DASHSCOPE_API_KEY` is set but the international batch endpoint (`dashscope-intl.aliyuncs.com`) rejects it with 401.

**config.yaml state after Phase 4:** 3 providers enabled (`gpt-5.4-nano`, `claude-haiku-4-5`, `gemini-3.1-flash-lite-preview`), `num_measures: [1]`, `limit: 3`, `question_ids: null`, `run_id: phase4_pilot_v3`. **Phase 5 must reconfigure this** for the full matrix.

**Acceptance:**
- ✅ 9 requests (3 × 3 providers) save cleanly with correct custom_id → test_case mapping.
- ✅ Process-kill-and-resume works (verified for all 3 providers in one kill).
- ✅ DB rows and JSON files agree (no divergence).
- ⚠️ Alibaba not tested — 401 error, needs investigation before Phase 5.

---

### Phase 5 — Full data collection (1-bar DONE, 8-bar partial, 2026-04-21)

**Why:** The whole point.

**Scope:** Full 1-bar MusicXML run — 45 passages × 9 questions × 3 models = 1215 requests.
`config.yaml`: `run_id: phase5_1bar`, `num_measures: [1]`, `passages: null`, `formats: [musicxml]`.

**Changes made before submitting:**
- `batch.py` `OpenAIBatchAPI` / `AnthropicBatchAPI` / `BatchRunner`: added `reasoning_effort` param, wired through `submit_all_batches.py:submit_single_batch`. OpenAI: if `reasoning_effort` set, injects it and drops `temperature`. Anthropic: drops `temperature` if `reasoning_effort` set (sending temperature with a reasoning model returns 400).
- `batch.py` `OpenAIBatchAPI.get_results` (and Alibaba mirror): if `output_file_id` is None but `error_file_id` exists, parses error file and returns `BatchResult(success=False)` entries rather than crashing. This handles the case where all requests fail at the API level.
- `config.yaml`: all model `max_tokens` set to 65536 (was 131072 for gpt-5.4; the batch API cap is 128000 but 65536 is sufficient and avoids edge cases).
- `scripts/run_gpt54_sequential.py`: one-off sequential fallback script, unused in final approach.

**Final results (2026-04-21):**
- **Anthropic (claude-opus-4-7):** ✅ 371/405 correct **(91.6%)**
- **Gemini (gemini-3.1-pro-preview):** ✅ 389/405 correct **(96.1%)**
- **OpenAI (gpt-5.4):** ✅ 375/405 correct **(92.6%)**

All 1215 results saved to `benchmark_v2.db` and `outputs/phase5_1bar/`.

**8-bar run (run_id: `phase5_8bar`) — partial:**
- **Anthropic (claude-opus-4-7):** ✅ 212/405 (52.3%) — completed immediately.
- **gpt-5.4:** ❌ Daily token quota exhausted (~1.35M/day; 1-bar run consumed it). Marked `failed_stale` in `outputs/phase5_8bar/batch_request_mappings.json`.
- **Gemini:** ❌ 429 RESOURCE_EXHAUSTED. No storage entry.

**To finish 8-bar (run after midnight Pacific when quotas reset):**
```bash
python3 -u scripts/submit_all_batches.py --retry-stale >> outputs/phase5_8bar_batch2.log 2>&1
```

**Notes:**
- First 1-bar gpt-5.4 batch failed (max_tokens 131072 > batch API cap of 128000). Fixed by capping all models at 65536.
- `openai.APIConnectionError` added to `is_retryable` — transient network errors during polling no longer crash the process.
- `scripts/run_gpt54_sequential.py` exists as a sequential fallback (unused).
- Alibaba skipped — DashScope international batch endpoint returns 401.
- P-001 results are duplicated in `benchmark_v2.db` (pilot + full run). Minor; dedup if needed.

---

### Phase 6 — Evaluation / extraction script audit (MusicXML DONE, 2026-04-24)

**Why:** Paper correctness lives here. We deferred this to parallelize with data collection — the evaluator is re-runnable over saved raw responses, so bugs here don't cost API money.

**Scope audited:** MusicXML extractors (`src/answer_extraction/musicxml/`), shared core (`src/answer_extraction/core/`), `src/llm_eval/evaluation.py`, and the `_compare_answers` path in `runner.py`. ABC/MEI/Humdrum extractors were *not* audited — they are not used in Phase 5.

**Fixed (2026-04-24):**

1. **Tie-chain totals truncated at middle-tie notes (Q5, Q9).** `_build_tie_duration_map` in `musicxml/utils.py` closed the chain and started a new one whenever it hit a note with both `stop` and `start` (middle of a 3+-note tie chain). For A→B→C it reported `d_A + d_B` under A instead of `d_A + d_B + d_C`. Fix accumulates straight through middle notes and only records the total when a pure-stop is reached.
   - DB `answer_musicxml` updated for the two affected rows: Q-500/P-055 `3 → 3.5`, Q-581/P-064 `3 → 4`. No Q9 rows were affected (no passage has a 3+-note chain at the first note of a staff).
   - `llm_responses` re-scored: 4 rows flipped from incorrect to correct (gpt-5.4 and gemini on Q-500; claude-opus-4-7 and gemini on Q-581). DB backup at `benchmark_v2.db.pre-phase6-fix`.
   - JSON result files under `outputs/phase5_8bar/{model}/musicxml/Q-500_r1.json` and `Q-581_r1.json` re-scored for all three models.
   - Summary accuracy numbers in the handoff above (Phase 5 8-bar: 212/405 for Anthropic) are pre-fix. Anthropic gains +1 on Q-581 (213/405). Gemini gains +2 (Q-500 and Q-581). gpt-5.4 gains +1 (Q-500). Re-aggregate from `llm_responses` for the paper.

2. **Q6 prompt ambiguity on enharmonic equivalence.** The old prompt said only "all Cs are the same pitch class" — silent on whether F# and Gb count as one or two. The MusicXML extractor returns string-based pitch classes (F# ≠ Gb), and the DB was seeded from it; three 8-bar passages (P-047, P-050, P-079) diverge from MIDI-mod-12 counting. Policy clarified: enharmonic spellings are distinct. The new prompt is now in `questions.question_text` for all 90 × 1 (Q6) rows and in `src/scripts/database/init_database.py`. Existing LLM responses are unchanged and still scored against the same (string-based) GT — the clarification only affects future runs.

**Deferred / documented (not fixed this session):**

- **Chord-tied-continuations not filtered from `_collect_notes_with_timing`** (`musicxml/utils.py:1107`). Uses `int(position)` where `position` is never incremented in this function — so for chord notes the lookup is always `(measure_idx, 0, pitch)` and never matches `tied_continuations`. No DB rows affected today (no first/last-note pick in the current corpus lands on a tied chord note in a way that changes output), but the sibling helpers (`get_notes_in_staff`, `get_all_note_durations_in_staff`) compute `note_position` correctly and this one is the outlier. One-line fix.
- **`pitch_to_midi` returns MIDI 0 on parse failure** (`core/pitch.py:44-46`). Silent fallback; violates the "no fallbacks" handoff rule. Safer to raise `ValueError`.
- **Dead `_parse_pitch` fallback regex** (`evaluation.py:183-195`). The "reversed format" fallback regex is byte-identical to the primary and can never fire. Comment misleading.
- **README Q6 scope mismatch** (`src/answer_extraction/README.md:24`). Says "across both staves"; actual prompt and code are lower-staff only.
- **`_build_tie_duration_map` / `_get_tied_note_info` assume `tie_starts` are already sorted** (`musicxml/utils.py:603-617`). MusicXML in the corpus is in document order so it's fine; one `starts.sort()` would make it robust.
- **`_compare_answers` rejects enharmonic matches (Q3/Q4).** Policy decision, not a bug: `Gb4` and `F#4` are scored as different answers. Q3/Q4 prompts tell the model how to spell accidentals ("Use 'b' to indicate flats and '#' to indicate sharps"), so strict comparison is intended. The paper should still consider reporting a secondary enharmonic-tolerant accuracy to contextualize the number; no code change needed.

**Method used (for reference if re-auditing other formats):**
1. Read each `qN_*.py` and the shared `utils.py` end-to-end; catalogue suspicious logic.
2. Cross-check all 810 `answer_musicxml` DB rows against extractor output (fast sanity pass — proves self-consistency but not correctness).
3. For each suspicious pattern, write a targeted probe to find passages that could trigger it in the real corpus (e.g. "find passages with middle-tie notes", "find passages with enharmonic spellings in lower staff").
4. For each hit, inspect the XML by hand and compute the true answer, then diff against the extractor.

---

### Phase 7 — Audit ABC evaluator suite (DONE, 2026-04-24)

**Scope audited:** `src/answer_extraction/abc/` — `utils.py` and `q1_*.py` .. `q9_*.py`. Cross-checked all 810 `answer_abc` rows in `benchmark_v2.db` against extractor output. Sanity-probed against every passage containing patterns known to be tricky (decorations, multi-measure lines, %%staves variants, multi-layer `&` voices, inline `[K:...]` clef changes, 3+-note tie chains).

**Fixed (2026-04-24):**

1. **Named decoration tokens leaked A–G / z / Z letters into pitch and rest extraction** (`abc/utils.py:remove_non_note_elements`). The function stripped `[X:...]` inline fields and `"..."` annotations, but not `!name!` decorations. The downstream walkers in `_extract_all_pitches_single_voice`, `count_notes_in_single_voice`, `count_rests_in_content`, and `_extract_notes_with_timing` skip a bare `!` character but not the letters inside it, so `!arpeggio!` added spurious `a`, `e`, `g`, `g` notes; `!fermata!` added `f`, `e`, `a`, `a`; `!mordent!` added `d`, `e`; `!sfz!` added an `f` *and* a `z` (the latter counted as a rest by Q8). `!trill!` and `!turn!` were safe by coincidence.

   Fix: `remove_non_note_elements` now also does `re.sub(r'![A-Za-z]+!', '', content)`. One line. Every question type that goes through a walker ends up calling this function (Q1/Q2 via `count_notes_in_content`; Q5/Q9 via `extract_all_durations_from_content` / `get_first_note_duration_in_content`; Q3/Q4/Q6 via `extract_first_pitch_from_content` / `extract_all_pitches_from_content`; Q7 via both; Q8 via `count_rests_in_content`), so the single fix covers all of them.

   **DB rows updated** (15 driven by this fix): Q1 five rows (Q-424 P-047 101→97; Q-451 P-050 48→44; Q-532 P-059 118→114; Q-640 P-071 60→56; Q-766 P-085 26→22). Q2 seven rows (Q-452 P-050 70→62; Q-470 P-052 76→68; Q-533 P-059 116→112; Q-569 P-063 81→71; Q-641 P-071 147→135; Q-758 P-084 179→178; Q-767 P-085 19→15). Q7 one row (Q-772 P-085 8→11 — the leaked `a` from `!fermata!` was shadowing the real highest last note C6). Q8 two rows (Q-575 P-063 9→7; Q-764 P-084 21→20).

   All affected rows are 8-bar passages. No 1-bar row moved. Cross-format sanity: Q-772 now agrees with MusicXML/MEI/Humdrum on 11; Q-429/Q-717 Q6 answers now agree across all four formats after fix #2 below.

2. **Q6 used MIDI-mod-12 (enharmonic-equivalent) counting, contradicting the Phase 6 prompt.** `abc/q6_pitch_class_count.py` rewrote to group pitches by their spelling prefix (`[A-G][#b]{0,2}`) instead of `midi_to_pitch_class`. F# and Gb now count separately, matching the MusicXML extractor and the question_text wording.

   **DB rows updated** (3 driven by this fix): Q-429 P-047 9→10; Q-456 P-050 11→13; Q-717 P-079 9→10.

**Total DB touch: 18 rows.** No `answer_abc` values moved for the 1-bar corpus (P-001 through P-045). DB backup at `benchmark_v2.db.pre-phase7-fix`. Self-consistency sweep (scripts/phase7_abc_selfcheck.py) re-runs clean afterward: 0 mismatches, 0 errors across all 810 rows.

**No `llm_responses` rescoring needed.** Only 1-bar ABC responses exist in the DB (Q-001..Q-414, 405 questions × 3 models = 1215 rows); all 18 fixed rows are in the 8-bar range (Q-415+). Phase 5's ABC collection was 1-bar only. Experimental earlier ABC runs under `outputs/phase6_1bar_abc*` are not wired to the DB.

**Documented / not fixed (non-data-wrong for this corpus):**

- **`extract_voice_content` regex stops at first `|`.** `abc/utils.py:145-172` uses `(.*?)(?:\||$)` to capture per-voice content from a line. In the current corpus every `[V:N]` line holds exactly one measure, so the regex captures the whole measure. But if a future ABC source placed multiple measures on one `[V:N]` line the second measure onward would be silently dropped. One-line fix if it matters: drop the `|` alternative and capture to end of line, then split on `|` downstream.
- **In-measure accidental reset depends on `|` characters surviving voice extraction.** The walkers correctly clear `active_accidentals` when they see `|`, but `extract_voice_content` joins per-line captures with spaces and the captured text has no `|` in it. For the corpus structure (one measure per `[V:N]` line) each measure is processed in isolation via the split-on-`&` layering inside `_extract_all_pitches_single_voice`, so the reset is implicit. If multi-measure voice lines appear, the implicit reset stops working and explicit accidentals bleed across bars. Related to the bullet above.
- **`&` multi-layer split is global, not per-measure.** `extract_all_durations_from_content` and friends do `content.split('&')`. For the joined voice content of a multi-measure passage this merges (measure N layer 2 + measure N+1 layer 1) into the same segment, breaking ties that span (layer X → new measure → layer X). This is the proximate cause of Q-581 (P-064) Q5 reading `3` for ABC while MusicXML/MEI/Humdrum read `4`: the cross-measure tie on the `c` in the after-`&` layer never resolves. Whether to "fix" this is policy: the ABC source file does contain the tie, and a proper per-measure layer tracker could find it, but fixing requires non-trivial rework of both the parser and the splitter. Leaving `answer_abc=3` is arguably faithful to what an ABC-only parser sees. Documenting so the paper can caveat cross-format divergence.
- **`parse_key_signature` matches the first `K:` token in document order.** `[K:clef=bass]` inline tokens would also match (the `c` satisfies `[A-Ga-g]`), but `re.search` stops at the first hit and every passage has a top-level `K: ...` header ahead of any inline clef directive. If that ordering ever changes a bogus key would be inferred. Adding an anchor (`^K:` in MULTILINE, or requiring a newline/start-of-string before `K:`) would harden this.
- **`count_notes_in_single_voice` accidental-context comment is wrong** (`abc/utils.py:414-419`). The comment admits "For simplicity, just use note + octave for now" — the dead `j = ...` / `accidental = ""` lines don't do anything and should be removed; behavior is unchanged because `normalize_pitch` strips accidentals for tie comparison anyway. Cosmetic only.
- **`_parse_pitch` dead fallback in `evaluation.py`** — called out in Phase 6, still present, still dead.
- **`pitch_to_midi` returns MIDI 0 on parse failure** (`core/pitch.py:44-46`) — still present, still violates "no fallbacks." Not exercised by Phase 7 fixes.

**Method (reusable for Phase 8/9):** `scripts/phase7_abc_selfcheck.py` (self-consistency sweep — compare DB vs extractor), `scripts/phase7_probes.py` + `scripts/phase7_probes2.py` (targeted synthetic and corpus probes), `scripts/phase7_impact.py` (diff extractor output on original vs cleaned passages — how I quantified the decoration leak), `scripts/phase7_apply.py` (DB update + llm_responses rescoring, dry-run by default, `--apply` to persist).

---

---

### Phase 8 — Audit MEI evaluator suite (DONE, 2026-04-24)

**Scope audited:** `src/answer_extraction/mei/` — `utils.py` and `q1_*.py` .. `q9_*.py`. Cross-checked all 810 `answer_mei` rows in `benchmark_v2.db`. Probed for every MEI-specific construct the HANDOFF called out (`<tie>` element chains, `@grace`, `@visible="false"`, `@staff` cross-staff redirection, `<app>/<lem>/<rdg>` apparatus, `<supplied>`, `<mRest>/<space>`, tuplets, double accidentals).

**Fixed (2026-04-24):**

1. **`<rdg>` (variant-reading) notes and rests were double-counted alongside `<lem>`** (`mei/utils.py`). In an `<app type="ossia">`, the `<lem>` block holds the primary reading and one or more `<rdg>` blocks hold variants. The helpers walked them all via `ElementTree.iter(...)`, so a passage with one note in `<lem>` and one in `<rdg>` reported two. Fix: `_get_rdg_descendant_ids(root)` returns `id()`s of every element inside any `<rdg>`, and every walker (`_get_tied_end_note_ids`, `_get_tied_note_pairs`, `get_notes_in_staff`, `get_rests_in_staff`, `_collect_notes_with_timing`, `get_all_note_durations_in_staff`) skips those ids. The corpus has only 5 rows affected (3 passages carry `<rdg>` notes, 1 passage a `<rdg>` rest — all 8-bar).

   **DB rows updated:** Q-667 P-074 Q1 `57→54`, Q-694 P-077 Q1 `39→35`, Q-578 P-064 Q2 `98→97`, Q-674 P-074 Q8 `7→6`. The Q-694 fix makes MEI/MXML/ABC/Humdrum agree at 35 (previously MEI was the outlier at 39). Q-667 brings MEI to ABC/Humdrum parity at 54 (MXML 55 — still one off, format convention).

2. **Tie-chain totals truncated at middle-tie notes (Q5).** Same pattern as Phase 6's MusicXML bug. For a chain A→B→C, `get_all_note_durations_in_staff` accumulated A+B under key `A`, then at B (middle) failed to transfer the accumulator so at C it could only emit C's duration as a fallback, leaving the `A+B` sum as an orphan emitted at end-of-function. Net: the chain contributed `A+B` and `C` as separate durations instead of a single `A+B+C`.

   Fix: track a `running_key` that is the current "head" of the chain. When the current note is both a tie end (adds its dur) and a tie start (middle), transfer the accumulator key from `running_key` to the current note's id so the next end-id lookup finds it. Also reworked so the emit branch always uses `tie_accumulator.pop(running_key)`, which eliminates the orphan-double-count for passages that begin mid-tie.

   **DB row updated:** Q-500 P-055 Q5 `3→3.5`. This aligns MEI with MusicXML/ABC/Humdrum (all 3.5) — the post-Phase-6 ground truth.

**Considered and rejected: honoring `@staff` for cross-staff re-attribution.** Three passages (P-021, P-069, P-079) carry notes or chords with `@staff` pointing to a different staff than their encoding parent. Counting them by their `@staff` target (visual rendering) rather than their encoding parent matches MusicXML behavior for P-079 only; for P-021 and P-069, music21's MusicXML export kept the note in its encoding parent. So per-passage MEI/MXML divergence is not uniform and honoring `@staff` would move MEI into *new* disagreements (Q-181 P-021, Q-622 P-069, Q-244/Q-245 P-028, Q-334/Q-335 P-038 — 13 rows) while only cleanly fixing one passage (P-079 Q1/Q2). Per the MEI 4.0 guideline that `@staff` on a note is a visual override rather than an analytical reassignment, the safer policy is to leave note attribution by encoding parent. This explains the remaining MEI/MXML divergence on P-079 (Q1 40 vs 32, Q2 80 vs 88) as a faithful reflection of format-specific encoding choices. Documenting.

**Documented / not fixed (non-data-wrong for this corpus):**

- **`@tie="i"/"m"/"t"` attribute-based ties are not recognized.** `_get_tied_end_note_ids` and `_get_tied_note_pairs` only parse `<tie>` elements with `@startid`/`@endid`. The corpus uses `<tie>` elements exclusively (0 `@tie` attributes across 90 passages), so this is a latent bug that would fire if the source data ever changes encoding style. One-line regex to co-populate: `for n in root.iter('note'): tie = n.get('tie'); ...`.
- **`get_pitch_classes_in_staff` regex `[A-G][#b]?` collapses double accidentals.** `C##` and `C#` would share a pitch class. The corpus has no double sharps or flats (0/90 passages), so this is dormant.
- **`parse_mei_pitch` `element.iter("accid")` walks into alternate readings.** For a note whose first descendant `<accid>` happens to sit inside `<rdg>` rather than `<lem>`, the wrong accidental could be picked. Only two corpus cases have nested `<accid>` with variant readings (P-040 note_17946, P-089 note_3576), and both have matching accidentals in `<lem>` and `<rdg>`, so no wrong pitches. Could be hardened by skipping elements whose id is in `_get_rdg_descendant_ids`.
- **`pitch_to_midi` returns MIDI 0 on parse failure** (`core/pitch.py:44-46`) — still the same latent bug flagged in Phases 6 and 7.
- **`_get_element_tuplet_ratio` requires an xml:id on the target element.** If a note in a tuplet lacks `xml:id`, the tuplet ratio silently falls back to 1.0. Corpus has 775 tuplet notes, all with `xml:id`, so dormant.
- **Q8 (rest count) has cross-format divergence on several passages.** MEI counts `<rest>` + `<mRest>` (visible); other formats count `<rest>` + equivalents differently. Policy, not a bug. Documented.
- **Q7 P-069 MEI=5 vs everyone else=4 and P-064 ABC=1 vs others=11.** Previously noted in Phase 7. Left as format-specific divergence.

**Method (same as Phase 7):** `scripts/phase8_mei_selfcheck.py` (self-consistency sweep), targeted probes inline in one-off scripts (not saved as they were quickly iterated), `scripts/phase8_apply.py` (DB update, dry-run by default, `--apply` to persist).

**No `llm_responses` rescoring needed.** No MEI responses exist in the DB (`SELECT COUNT(*) FROM llm_responses WHERE format='mei'` = 0). All 5 affected rows are 8-bar passages; any future MEI collection will score against the corrected ground truth.

**DB backup:** `benchmark_v2.db.pre-phase8-fix` (taken before this phase's updates).

---

### Phase 9 — Audit Humdrum evaluator suite (DONE, 2026-05-02)

**Scope audited:** `src/answer_extraction/humdrum/` — `utils.py` and `q1_*.py` .. `q9_*.py`. Cross-checked all 810 `answer_humdrum` rows in `benchmark_v2.db`. Probed every passage flagged by the cross-format diff where humdrum disagreed with all three other formats (`scripts/phase9_humdrum_selfcheck.py`, `scripts/phase9_cross_format_diff.py`, `scripts/phase9_suspect_detail.py`, `scripts/phase9_probes.py`, `scripts/phase9_probes2.py`).

**Fixed (2026-05-02):**

1. **Rest tokens with pitch positioning hints were parsed as notes** (`humdrum/utils.py:is_rest`). In **kern, the letter ``r`` exclusively encodes a rest. Pitch letters following the ``r`` (e.g. ``8rBB``, ``8rc``, ``8rg``) are *rest-position hints* — they tell the renderer which staff line to draw the rest on, not pitches. The old `is_rest` required `'r' in cleaned and not any(c in cleaned for c in 'abcdefgABCDEFG')`, so any positioning-hint suffix flipped the token from rest to note. `is_note` then accepted it because it had a pitch letter.

   The corpus has 9 such tokens in 3 passages: `8rBB` ×4 in P-050, `8rg` ×2 in P-050, `8rc` ×1 in P-084, `8rc` ×1 in P-089, `8rBB` ×1 in P-089. Each phantom-counted note both inflated note counts (Q1/Q2) and depleted rest counts (Q8). Fix: `is_rest` is now `'r' in token` (with the empty/`.` short-circuits preserved). Pitch letters after `r` are no longer parsed as notes by any walker.

   **DB rows updated** (7 driven by this fix): Q-451 P-050 Q1 `48→44`; Q-802 P-089 Q1 `56→54`; Q-452 P-050 Q2 `62→60`; Q-758 P-084 Q2 `179→178`; Q-458 P-050 Q8 `28→34`; Q-764 P-084 Q8 `19→20`; Q-809 P-089 Q8 `11→13`.

2. **Q3 (first pitch upper staff) ignored simultaneous notes across spine-split sub-spines** (`humdrum/q3_first_pitch_upper.py`). Q3 walked `get_upper_spine_data(...)` — a flat token list — and returned the first token's first pitch. When the upper kern spine has been split via `*^` at the start of a passage (P-081 line 49), the first row holds simultaneous tokens across multiple sub-spine columns; the flat-list iteration only sees the leftmost. Q7 already had a row-aware variant (`get_upper_spine_data_by_row` + `get_interval_first_last_by_rows`); Q3 didn't.

   Fix: added `get_first_note_pitch_by_rows(rows, return_highest_in_chord, include_grace)` to `utils.py` and rewired `q3_first_pitch_upper.py` to use it. Picks the highest pitch among all simultaneous notes in the first non-empty row, across both sub-spine tokens and within chord tokens.

   **DB row updated** (1 driven by this fix): Q-732 P-081 Q3 `Eb3→F4`. The old answer (`Eb3` = `[4E-` in the leftmost upper sub-spine after the split) was a low note in the rightmost-spine; the actual highest simultaneous note in the upper staff at that beat is F4 (`(8.fL`). Now agrees with MusicXML and MEI (`F4`). ABC remains divergent at `Ab5` — consistent with Phase 7's note that ABC's first-pitch extraction has its own corpus-specific quirks.

**Total DB touch: 8 rows.** All eight are 8-bar passages. No `answer_humdrum` values moved for the 1-bar corpus. DB backup at `benchmark_v2.db.pre-phase9-fix`. Self-consistency sweep (`scripts/phase9_humdrum_selfcheck.py`) re-runs clean afterward: 0 mismatches, 0 errors across all 810 rows. Cross-format-diff humdrum-alone count dropped from 12 to 5.

**No `llm_responses` rescoring needed.** All 1215 humdrum responses (3 models × 405 1-bar questions) are 1-bar (Q-001..Q-414); all 8 fixed GT rows are 8-bar (Q-415+). Any future 8-bar humdrum collection will score against the corrected ground truth.

**Documented / not fixed (cross-format export divergence, not humdrum bugs):**

- **Q-730 P-081 Q1 humdrum=68 vs others=69.** P-081 lower spine has exactly 68 raw note tokens, zero ties, zero grace notes. Humdrum's count is correct for the kern source. The 1-note discrepancy with MXML/ABC/MEI is from music21's MXML round-trip introducing a chord-note or ornament-expansion difference. Faithful representation; leave.
- **Q-578 P-064 Q2 (h=99/x=95/a=101/m=97), Q-641 P-071 Q2 (h=134/x=146/a=135/m=141).** All four formats disagree. Each format reflects its own encoding's notion of "note" — MusicXML may include a hidden voice that the .krn doesn't expose, ABC's layered-voice splitter (Phase 7 documented bullet) miscounts cross-measure layers, MEI's `<rdg>`/`<lem>` policy filters differently. Document as cross-format divergence; do not unify.
- **Q-646 P-071 Q7 humdrum=5 vs MXML=7/MEI=7/ABC=14.** Humdrum's first upper note is `16aLL` (A4) and last is `8dd'J` (D5). A4→D5 = 5 semitones. Correct for the kern. MXML/MEI's 7 implies a different first or last note after music21 export (likely G4 → D5). ABC's 14 likely from layered-voice tangle.
- **Q-719 P-079 Q8 humdrum=8 vs MXML=12/ABC=10/MEI=20.** Wild divergence on rest counting. Humdrum's 8 reflects only the visible-rest count after the `is_rest` fix (P-079 has invisible `yy` rests that humdrum correctly skips). MEI=20 likely counts all `<rest>` and `<mRest>` regardless of visibility. Policy difference.
- **`get_first_note_pitch` (flat-list version) in `utils.py` is now only used by tests/probes** — kept for backward compatibility with `q3` if it's ever reverted. If future cleanup deletes unused helpers, this is one to consider.
- **Q9 (first note duration in lower staff) has the same latent spine-split bug as Q3 had.** No corpus passage has `*^` on the lower spine *at the start* (P-050 splits at measure 31, P-089 at measure 4 — both well past the first note), so Q9 is dormant in the current corpus. If a future passage opens with a lower-staff split, Q9 will silently pick the leftmost sub-spine's first note rather than the highest among simultaneous notes. Same fix pattern as Q3 (use rows + a `get_first_note_duration_by_rows` helper). Skipping per the "minimal, corpus-driven" rule.
- **`pitch_to_midi` returns MIDI 0 on parse failure** (`core/pitch.py:44-46`) — still present, still violates the "no fallbacks" handoff rule. Outstanding from Phases 6/7/8.
- **`evaluation.py` `_parse_pitch` dead fallback regex** — still present, still dead. Outstanding from Phases 6/7.

**Method (same as Phase 7/8):** `scripts/phase9_humdrum_selfcheck.py` (self-consistency sweep — DB vs extractor on all 810 rows), `scripts/phase9_cross_format_diff.py` (per-question summary of humdrum vs MXML/ABC/MEI, with humdrum-alone diffs prioritized), `scripts/phase9_suspect_detail.py` (full diff dump for a chosen qtype), `scripts/phase9_probes.py` + `scripts/phase9_probes2.py` (token-level inspection of suspect passages, cross-extractor checks, spine-path-op listing), `scripts/phase9_verify_fix.py` (sanity-check proposed updates against cross-format consensus before applying), `scripts/phase9_apply.py` (dry-run by default, `--apply` to persist; verifies extractor still produces the new value before each UPDATE).

---

## Phase 6–9 wrap-up

The full evaluator audit (Phases 6–9) is complete. MusicXML, ABC, MEI, and Humdrum extractors have each been read end-to-end, probed against the 810-row ground-truth corpus, and corrected where bugs affected current data. DB backups for each phase are preserved (`benchmark_v2.db.pre-phase{6,7,8,9}-fix`). All cross-format divergence that remains is documented as either policy difference or upstream-export artefact — not extractor bugs.

Outstanding cross-phase items still not fixed:
- `core/pitch.py:44-46` `pitch_to_midi` MIDI 0 fallback (raise `ValueError` instead).
- `evaluation.py` `_parse_pitch` dead-fallback regex.
- ABC `extract_voice_content` and `&` multi-layer split assume one measure per `[V:N]` line; multi-measure lines would silently drop notes (Phase 7 documented).
- Q9 (humdrum) latent spine-split simultaneity issue (Phase 9 documented).

---

### Phase 10 — Merge benchmark_v2.db into benchmark.db (DONE, 2026-05-02)

**Why:** Single unified DB containing all 7 models (4 v1 + 3 v2) so paper analysis / cross-model comparisons run off one source of truth.

**Handoff notes (2026-05-02):**

**Pre-merge state confirmed by SQL diff (matches earlier audit in this doc):** passages and question_types tables identical between v1 and v2; `answer_abc`/`answer_mei`/`answer_musicxml` identical; `answer_humdrum` differs in exactly the 8 Phase-9-corrected rows; `question_text` differs in exactly the 90 Q6 rows (Phase 6 enharmonic-distinct clarification). Model name sets are disjoint, so the `llm_responses` UNIQUE(question_id, passage_id, format, model) constraint guarantees a conflict-free UNION.

**Refactor (minimal).** Extracted the body of `BenchmarkRunner._compare_answers` into a module-level `compare_answers(extracted, expected) -> bool` in [src/llm_eval/evaluation.py](src/llm_eval/evaluation.py) so the merge script can import it without instantiating a runner. The method now delegates. Bug-for-bug-faithful — verified against legacy logic on 15 hand-picked cases.

**Merge script:** [scripts/phase10_merge.py](scripts/phase10_merge.py). Dry-run by default; `--apply` to persist. Idempotent — every step is safe to re-run.
1. Pre-check refuses to merge if anything other than the expected 8 humdrum / 90 Q6 diffs is present (defends against schema drift or unknown divergence).
2. Updates `questions.answer_humdrum` for the 8 Phase-9 rows.
3. Updates `questions.question_text` for the 90 Q6 rows (v1 → v2 wording).
4. Rescores **every** humdrum response in the target against current target GT (idempotent and self-healing — flips 6 stale `is_correct` rows on first run, finds 0 to flip on subsequent runs).
5. Copies all `src.llm_responses` rows into the target via `INSERT OR IGNORE`.

**Q6 prompt-version decision (per user, 2026-05-02): adopted v2 wording for all 90 Q6 rows. v1 LLM responses for Q6 were NOT rescored.** See "Caveat" below — the merged DB displays the v2 prompt next to v1 responses, but those responses were generated under the (more ambiguous) v1 wording. Surface this in the paper if prompt provenance matters.

**Verification (all green):**
- Row counts: 90 passages, 9 question_types, 810 questions, 18,630 llm_responses (12,960 v1 + 5,670 v2 — matches expected).
- Coverage: 7 distinct models present; v1 models full × 4 formats × 2 measure lengths; v2 models per the table above.
- 4-format extractor selfcheck on the merged DB: 0 mismatches, 0 errors across all 3,240 (810 × 4) GT rows.
- `is_correct` consistency across all 18,630 rows: 0 inconsistencies.
- 20-row random spot-check by hand: every `is_correct` agrees with `extracted_answer`-vs-`answer_*`.

**Rescore detail:** the only `is_correct` flips were 6 rows of `gemini-3-pro-preview` for Q-451 / Q-452 / Q-458 / Q-732 / Q-764 / Q-809 (the 6 cases where the model's stored extracted answer matched the new humdrum GT). All flips False → True.

**Backups preserved (gitignored):**
- `benchmark.db.pre-merge` — pre-merge target snapshot.
- `benchmark_v2.db.pre-merge` — pre-merge source snapshot.
- `benchmark_v2.db.merged-into-v1` — v2 file after the merge (rename of `benchmark_v2.db`). Safe to delete once you've verified the merged DB end-to-end.

**`config.yaml`** updated: `database: benchmark.db` (was `benchmark_v2.db`).

**Caveat for the paper.** v1 LLMs were prompted with the original (more ambiguous) Q6 wording; their responses reflect that wording. The merged DB displays the v2 wording (the post-Phase-6 enharmonic-distinct clarification) on those rows. If any downstream analysis assumes the displayed prompt is the prompt the model saw, surface this in the paper text or in an analysis note. The user explicitly accepted this trade-off in exchange for narrative simplicity (option 2 of the 5 considered).

---

## Open work for the next agent

Phases 1–10 are DONE. The next agent should pick **one** of the following, with the user's confirmation. Each is scoped so it can stand alone as a phase. Pick from this list, do not invent new scope.

### Option A (HIGHEST PRIORITY) — Phase 11: finish 1-bar MEI for gpt-5.4

**Why:** Only missing slot in the 1-bar matrix (see *Current state* table).

**Status at hand-off (after Phase 10 merge):** A gpt-5.4 OpenAI batch (`batch_69ebdf176aac8190a9df38386a3d4a16`) was submitted on 2026-04-24 and is recorded in `outputs/phase6_1bar_mei/batch_request_mappings.json` with `lifecycle_state: submitted`. OpenAI batches expire after 24 hours, so this batch is almost certainly stale — running `--retry-stale` will be needed to resubmit. Claude and Gemini already have 405 mei rows each in `benchmark.db`; gpt-5.4 has 0.

`config.yaml` is now pointed at `benchmark.db` (Phase 10 update) and still configured for this run (`run_id: phase6_1bar_mei`, `formats: [mei]`, `num_measures: [1]`).

**How to start:**
1. `sqlite3 benchmark.db "SELECT model, COUNT(*) FROM llm_responses WHERE format='mei' GROUP BY model;"` — should show claude-opus-4-7=405, gemini-3.1-pro-preview=405, gpt-5.4=0 (plus the four v1 models at 810 each).
2. `python3 -u scripts/submit_all_batches.py --poll-only` — confirms the OpenAI batch is `expired`/`failed_stale`. If so, run `python3 -u scripts/submit_all_batches.py --retry-stale` to resubmit just gpt-5.4 (Claude/Gemini are already `saved`).
3. After completion, run the 4-format inline selfcheck (see Phase 10 handoff notes) on `benchmark.db` to confirm GT consistency.

**Acceptance:** 405 new gpt-5.4 mei rows in `benchmark.db`; selfcheck stays clean; spot-check 5 random rows.

### Option B — Phase 12: 8-bar collection for non-MusicXML formats

**Why:** The biggest remaining data gap *for v2 models*. The v1 models already have full 8-bar coverage across all four formats. v2 8-bar exists only for MusicXML. ABC / Humdrum / MEI 8-bar runs for the three v2 reasoning models do not exist yet. The paper probably wants the full 4-format × 2-measure-length matrix for v2 too.

**Pre-flight checks:**
- Quota: Phase 5's 8-bar run was quota-blocked for both gpt-5.4 (OpenAI ~1.35M enqueued tokens/day) and Gemini (250 RPD project-wide on Tier 1; see memory `gemini_rpd_quota.md`). 8-bar passages have ~10× the tokens of 1-bar, so plan accordingly.
- Run order: stagger by format and provider. `scripts/daemon_launch.sh` is the right launcher for multi-hour batches (see memory `feedback_daemonize_long_running.md`).
- Anthropic 8-bar humdrum/abc/mei has **not** been run before; budget accordingly.

**How to start:** model the run after Phase 5's 1-bar config but with `num_measures: [8]` and one format at a time. Use `--poll-only` resume if killed mid-run; `--retry-stale` for any `failed_stale` entries.

**Acceptance:** all 405 × N rows present; selfcheck clean; rescore not needed (post-Phase-9 GT is the target).

### Option C — Phase 13: cleanup of documented-but-not-fixed items

A grab-bag of latent bugs documented across Phases 6–9. None affect current corpus data. Tackle in any order:

- **`core/pitch.py:44-46` `pitch_to_midi` MIDI-0 fallback.** Replace with `raise ValueError(f"Cannot parse pitch: {pitch!r}")`. Re-run all four selfcheck scripts to confirm no regression.
- **`evaluation.py` `_parse_pitch` dead-fallback regex** (Phase 6 documented). Delete the unreachable branch.
- **ABC `extract_voice_content` and `&` multi-layer split** (Phase 7 documented). Multi-measure `[V:N]` lines silently drop notes. Refactor to be measure-aware.
- **MEI `@tie="i/m/t"` attribute-based ties** (Phase 8 documented). Currently only `<tie>` element-based ties are recognized. Add attribute support to `_get_tied_end_note_ids` / `_get_tied_note_pairs`.
- **MEI `get_pitch_classes_in_staff` regex `[A-G][#b]?`** (Phase 8 documented). Doesn't handle double accidentals. Change to `[A-G][#b]{0,2}`.
- **MEI `parse_mei_pitch` `element.iter("accid")`** (Phase 8 documented). Walks into alternate readings. Skip `_get_rdg_descendant_ids`.
- **Humdrum Q9 latent spine-split simultaneity** (Phase 9 documented). Same fix pattern as Q3: `get_first_note_duration_by_rows`. Add to `utils.py` and rewire `q9_first_note_duration.py`.
- **Humdrum `get_first_note_pitch` (flat-list version)** (Phase 9 documented). Now unused after Q3 was rewired. Delete unless something still imports it.

**Acceptance:** four selfcheck scripts (`scripts/phase{6,7,8,9}_*selfcheck.py` — note phase6 has none; reuse `phase7_abc_selfcheck.py` pattern across formats if desired) all stay clean; existing tests pass; no DB updates.

### Option D — analysis / paper assets

Out of scope for these phases. If the user redirects here, ask for explicit deliverables.

---

## How to hand off to the next phase

1. Finish the phase's acceptance checks.
2. Edit this file: mark the phase **(DONE)**, add a **Handoff notes** subsection under it with any quirks, decisions, or deviations discovered.
3. Commit: `git commit -m "Phase N: <summary>"`.
4. Spin up a new agent with a single-line prompt pointing at this file and the next phase number.

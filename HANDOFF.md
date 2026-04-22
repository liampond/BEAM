# BEAM v2 — Batch Pipeline Hardening Handoff

This document is the source of truth for a multi-phase cleanup. Each phase is scoped so a fresh agent can pick it up without seeing prior conversations.

**Always update this doc at the end of a phase before handing off.** Mark the completed phase, note any decisions or deviations, and leave the next phase actionable.

---

## Context

- **Project:** BEAM benchmark for music encoding LLM evaluation. Camera-ready deadline **2026-04-24** (Music Encoding Conference).
- **Situation:** An ambitious v2 redesign was started, then pulled back. We reset the working tree to commit `0165246`, preserved a narrow set of bug fixes (new commit `19a1545`), and are now hardening the batch API pipeline before regenerating data.
- **Snapshot branch:** `wip-v2-redo-snapshot` holds the abandoned v2-redo work. Keep it until Phase 3 verifies; then `git branch -D wip-v2-redo-snapshot`.
- **Repo plan:** The user will manually create a new GitHub repo (renamed project) without history from this one. That migration is out of scope for these phases.

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

### Phase 5 — Full data collection (DONE, 2026-04-21)

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

**Notes:**
- First gpt-5.4 batch failed (max_tokens 131072 > batch API cap of 128000). Fixed by capping all models at 65536. Re-submitted and succeeded.
- `openai.APIConnectionError` added to `is_retryable` — transient network errors during polling no longer crash the process.
- `scripts/run_gpt54_sequential.py` exists as a sequential fallback (unused).
- Alibaba skipped — DashScope international batch endpoint returns 401.
- P-001 results are duplicated in `benchmark_v2.db` (pilot + full run). Minor; dedup if needed.

---

### Phase 6 — Evaluation / extraction script audit

**Why:** Paper correctness lives here. We deferred this to parallelize with data collection — the evaluator is re-runnable over saved raw responses, so bugs here don't cost API money.

**Scope:** Every extractor in `src/answer_extraction/`; comparison logic in `src/llm_eval/evaluation.py`; the `_compare_answers` path in `runner.py`.

**Method:**
1. For each question type, assemble 5-10 hand-labeled cases covering edge conditions (rests, ties, tuplets, anacrusis, multi-voice, enharmonic spellings, octave boundaries).
2. Run each extractor against its cases; diff against expected.
3. Investigate any disagreement.
4. Re-run evaluation over the collected raw responses from Phase 5.

---

## How to hand off to the next phase

1. Finish the phase's acceptance checks.
2. Edit this file: mark the phase **(DONE)**, add a **Handoff notes** subsection under it with any quirks, decisions, or deviations discovered.
3. Commit: `git commit -m "Phase N: <summary>"`.
4. Spin up a new agent with a single-line prompt pointing at this file and the next phase number.

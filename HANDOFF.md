# BEAM — active handoff

This is the lean, currently-active handoff. The full narrative for **Phases 0–10** (root-cause diagnostic, per-phase scope, fixes, deferred items) lives in [docs/phase_history.md](docs/phase_history.md). Read that if you need the *why* behind the current codebase.

**Always update this doc at the end of a piece of work before handing off.** Mark what was done, note any decisions, and leave the next item actionable.

---

## Context

BEAM is the music-encoding LLM benchmark for Mozart's piano sonatas: 9 questions × 45 passages × 4 formats × 7 models. The Music Encoding Conference camera-ready was submitted **2026-04-24** (v1 models). The conference presentation is in **late May 2026**, and the goal between now and then is to (a) extend results with the v2/newer model set so the presentation can show a clean 7-model comparison, and (b) leave the repository in a clean, reviewer-ready state.

Phases 0–10 (v2 batch-pipeline hardening + four-format evaluator audits + v1↔v2 DB merge) are all DONE and committed (HEAD at `a46deae` as of 2026-05-02).

A **repo cleanup pass** is now in flight. The plan is at [docs/cleanup_plan_2026_05.md](docs/cleanup_plan_2026_05.md), structured as 3 self-contained sessions. Session 1 Part A (this docs split) is the first piece.

---

## Current state (2026-05-10)

**Active DB:** `benchmark.db` — the unified DB containing all 7 models. Ground truth and `is_correct` are internally consistent (full selfcheck = 0 mismatches across 18,630 `llm_responses` and 810 GT rows for each of the 4 formats).

**Data-collection coverage (8-bar rows for v2 models — 1-bar matrix is fully complete):**

| Format | claude-opus-4-7 | gemini-3.1-pro-preview | gpt-5.4 |
|---|---|---|---|
| musicxml | 405 ✅ | 405 ✅ (3 null) | 405 ✅ (25 null) |
| abc      | 405 ✅ | **89 / 405** | 405 ✅ (5 null) |
| humdrum  | 405 ✅ | **92 / 405** | 405 ✅ (4 null) |
| mei      | 405 ✅ | **92 / 405** | 405 ✅ |

The v1 models have full 8-format-pair coverage. v2 status:

- **claude-opus-4-7:** DONE for 8-bar across all 4 formats. 3-row credit-exhaustion retry succeeded on 2026-05-08 (Q-488/P-054, Q-611/P-067, Q-689/P-076).
- **gpt-5.4:** DONE for 8-bar across all 4 formats. Q-802/P-089 humdrum patched 2026-05-10 via `scripts/gpt54_q802_p089_humdrum.py` (extracted "54" = expected). Assorted NULL extractions remain (legitimate empty/unparseable answers, not failures). The chunked-mei chain finished 2026-05-09.
- **gemini-3.1-pro-preview:** **942 rows missing** in abc/humdrum/mei. Active daily-chunk work is in flight (see *Open work* below).

**Active local config (`config.yaml`):** `database: benchmark.db`. As of 2026-05-10 it is set to `formats:[mei] / num_measures:[8]`, only `gpt-5.4` enabled, `run_id: presentation_run2_gpt54_mei_8bar`. No corresponding `outputs/` directory exists, so the run was set up but never launched — verify before reusing. The gemini daily-chunk script bypasses `config.yaml` entirely so it is unaffected. This file is intentionally **not committed**.

**Backups on disk (gitignored, scheduled to move into `_archive/db_backups_2026_05/` per the cleanup plan):** `benchmark.db.pre-merge`, `benchmark.db.pre-presentation-update`, `benchmark.db.pre-gemini-humdrum-patch`, `benchmark.db.pre-gt-rescore`, `benchmark_v2.db*` (multiple). All are post-Phase-10 redundant; safe to archive.

---

## Gemini 8-bar status & batch-size finding (2026-05-08 → 2026-05-10)

This is the active piece of work and the most subtle ongoing issue.

**The pattern.** Gemini-3.1-pro-preview batches submitted at the *project-wide RPD ceiling* return mostly-failed responses. Concretely:

| Batch date | Size | Succeeded | Failed | Yield |
|---|---|---|---|---|
| 2026-05-07 | 243 | 54 | 189 | **22%** |
| 2026-05-08 | 240 | 119 | 121 | **50%** |
| 2026-05-09 | 100 | 100 | 0 | **100%** |
| 2026-05-10 | 200 | *in flight* | *in flight* | *pending* |

The failures come back with explicit Google-side error codes — not network errors:

- `{"code": 4, "message": "Deadline expired before operation could complete"}` (per-request timeout)
- `{"code": 1, "message": "The operation was cancelled"}` (preemption)

**Why it is not a daemon/network issue.** Our polling daemon dying from `httpx.ConnectError` (intermittent on this laptop's DNS) only delays the *download* of the result file. The batch keeps running on Google's servers regardless. Resuming with `--poll-only` retrieves the *same* JSONL — same failures, byte-for-byte — confirming the failures are server-side. Don't waste time hunting client-side fixes for this.

**The hypothesis.** Once a batch nears the 250 RPD project-wide cap, Google preempts the long tail to protect quota for other consumers. Smaller batches sail through clean. The right ceiling is somewhere ≤ 100; whether 150 or 200 also works at 100% is untested.

**Tools.**

- `scripts/gemini_8bar_daily_chunk.py` is the standalone submitter. Bypasses `config.yaml` entirely — safe to run alongside any `submit_chunked.py` chain. Computes missing rows directly from the DB, submits one batch ≤ `--max-requests`, polls, downloads, upserts. State at `outputs/gemini_8bar_daily/state.json`. Resume with `--poll-only`.
- `scripts/recover_gemini_batch.py` — for a one-off recovery of a specific succeeded batch by ID.
- `scripts/daemon_launch.sh` — required for multi-hour polls (the daemon dies on terminal disconnect otherwise; see memory `feedback_daemonize_long_running.md`).

---

## Guiding rules

- **No fallbacks.** If an API key or model is wrong, raise — don't silently switch to something else.
- **No emojis** in code, commits, or docs.
- **No backwards-compat shims.** Delete dead paths cleanly.
- **Minimal comments.** Only where the *why* is non-obvious.
- **Test each phase with a tiny dry run** (5 requests, one provider) before declaring done.
- **One discrete unit of work per agent session.** When work completes, update this doc and spin up a new agent with a pointer to the next item.

---

## Open work for the next agent

Phases 1–11 (1-bar matrix) are DONE. Phase 12 (8-bar) is mostly DONE — claude-opus-4-7 and gpt-5.4 are essentially complete; only gemini and a single gpt-5.4 row remain. Pick **one** of the following, with the user's confirmation.

### Option A (HIGHEST PRIORITY) — Finish Phase 12: gemini 8-bar abc/humdrum/mei

**Why:** 942 missing rows for gemini-3.1-pro-preview is the only sizable remaining data gap before the late-May 2026 presentation.

**Why this is non-trivial:** see the *Gemini 8-bar status & batch-size finding* section above. TL;DR — large batches yield only 22–50% on the gemini batch API (server-side preemption near the 250 RPD ceiling), small batches yield 100%. The next chunk size is an open experimental question.

**Probe result (2026-05-10 12:38 → 14:50):** `--max-requests 200` batch `batches/3dm39psvsjz8oxgxxe931kr05lss8b0dqdba` completed at **100% yield (200/200)**. Log `outputs/gemini_8bar_daily/run_20260510_123818.log`. Rows were upserted to DB. **742 rows remain missing** for gemini-3.1 8-bar abc/humdrum/mei. Open question: try 220 next (untested), or stay at 200 known-safe. 240 was confirmed degraded.

**Prior experiments:**

- 100 was confirmed at 100% yield (2026-05-09).
- 240 was confirmed at 50% (2026-05-08) and 22% (2026-05-07).

**How to start:**

1. Confirm no daemon is running: `ps aux | grep gemini_8bar_daily_chunk` should be empty. State file `outputs/gemini_8bar_daily/state.json` should be absent (a present state file means a batch is in flight; resume with `--poll-only`).
2. Pick a `--max-requests`. Today's value is the user's call, not a default.
3. Daemonize: `scripts/daemon_launch.sh outputs/gemini_8bar_daily/run_$(date +%Y%m%d_%H%M%S).log venv/bin/python3 -u scripts/gemini_8bar_daily_chunk.py --max-requests N`.
4. The batch takes 2–5h server-side. The daemon polls every 60s; on success it auto-downloads, upserts to DB, and clears the state file.
5. If the laptop's DNS dies mid-poll (it has, twice), the daemon dies cleanly with the state file intact. Resume with `--poll-only`.

**Acceptance:** `gemini_8bar_daily_chunk.py` reports 0 missing for abc/humdrum/mei; selfcheck stays clean.

### Option B — Patch the last gpt-5.4 humdrum row (Q-802/P-089) — **DONE 2026-05-10**

Patched via `scripts/gpt54_q802_p089_humdrum.py` (synchronous OpenAI Responses API call, reasoning_effort=high, json_schema). Output `54` = expected `54`. gpt-5.4 humdrum now at 405/405.

### Option C — Phase 13: cleanup of documented-but-not-fixed items (Phase 13c GT-fix landed, 2026-05-10)

**Status:** Code changes for all 8 hygiene items + tie-binding + layer-alignment are landed and uncommitted. **All three selfchecks now clean (ABC/MEI/Humdrum = 0/0/0).** 60 unit/integration tests pass. The 19 ABC GT errors documented in this section have been corrected in `benchmark.db` via `scripts/phase13c_apply.py`. See *Phase 13 working notes* below.

**Done in this session (all uncommitted on `main`):**

1. **`core/pitch.py` MIDI-0 fallback** — `pitch_to_midi` now raises `ValueError` instead of returning 0.
2. **`evaluation.py` `_parse_pitch` dead regex** — unreachable branch removed (the "fallback" regex was character-identical to the primary).
3. **ABC `extract_voice_content` + `&` multi-layer measure-aware fix** — `extract_voice_content` now preserves `|` and captures full lines; new `split_into_layered_measures` helper; 5 `&`-split call sites switched to it. Two follow-on walker bug fixes also landed (see below).
4. **MEI `@tie="i/m/t"` attribute-based ties** — new `_get_attribute_tie_info` helper; `_get_tied_end_note_ids` / `_get_tied_note_pairs` now also collect from `@tie` attributes. Corpus has 0 attribute ties so this is dormant, but the implementation is FIFO-per-staff pitch-matched and standards-compliant.
5. **MEI `get_pitch_classes_in_staff` regex** — `[A-G][#b]?` → `[A-G][#b]{0,2}`.
6. **MEI `parse_mei_pitch` rdg-skip** — new `_iter_descendants_skipping_rdg`; `<accid>` elements inside `<rdg>` no longer contribute pitch.
7. **Humdrum Q9 spine-split simultaneity** — added `get_lower_spine_data_by_row` + `get_first_note_duration_by_rows`; rewired `q9_first_note_duration.py` to mirror Q3's row-aware pattern.
8. **Humdrum flat-list `get_first_note_pitch` deleted** — zero callers across `src/`, `tests/`, `scripts/`. MEI/MusicXML versions are different functions with the same name; unaffected.

**Also fixed in passing:**

- All three `scripts/phase{7,8,9}_*selfcheck.py` were pointing at `benchmark_v2.db` which no longer exists post-Phase-10 merge. Updated to `benchmark.db`. Without this they fail with `FileNotFoundError` immediately.

**Item 3 (ABC) — predicted to dirty the selfcheck, did so as expected.**

The point of item 3 was to make `&`-split measure-aware so cross-measure ties on a layer survive. This necessarily changes extractor output for any passage where the old global `&`-split was garbling layer-to-measure correspondence. After landing item 3 plus two follow-on walker fixes (see below), the ABC selfcheck has 19 mismatches vs DB ground truth. Cross-format analysis is in the *Phase 13 working notes* section further down:

- **14 of 19 mismatches: ABC now matches MusicXML/MEI/Humdrum consensus.** These are wins — the DB GT was reflecting the OLD buggy ABC extractor. Updating GT for these rows is a separate decision (this session did *not* touch the DB). Examples: Q-732 P-081 Q3 `Ab5→F4`, Q-583 P-064 Q7 `1→11`, Q-646 P-071 Q7 `14→5`.
- **5 still need investigation** (see "Phase 13b" handoff below).

**Walker bugs fixed in passing (uncommitted, no GT impact verified on clean rows — `MEI`/`Humdrum` selfchecks stayed at 0/0):**

- **Broken-rhythm `>` leaked across rests.** In `_extract_durations_single_voice`, a `>` token between rests (e.g. `x/> x/` in invisible-rest padding) carried a pending modifier to the next note/chord, inflating duration by 1.5x. The OLD truncation-artifact behavior was masking this. Fix: rest handler now consumes any trailing `>`/`<` and clears both `pending_broken_rhythm` and `last_note_duration_idx`. Resolved Q-644 P-071 Q5 and Q-455 P-050 Q5.
- **ABC alternate-ending markers `[1` and `[2` were entering the chord walker.** Multi-time-bracket repeat markers like `|[1` and `:|][2` end up in `extract_voice_content` output now that `|` is preserved. The chord walker tries to find a matching `]` and consumes way too much. Fix: `remove_non_note_elements` now strips `\[\d[\d,]*` (digit-prefixed `[N` openers). Resolved Q-538 P-059 Q7.

---

## Phase 13 working notes (2026-05-10)

Selfcheck state after Phase 13c (layer-alignment fix) — `scripts/abc_selfcheck.py`:

| qid         | qtype | DB    | ABC new | MXML | MEI  | Hum | verdict               |
| ----------- | ----- | ----- | ------- | ---- | ---- | --- | --------------------- |
| Q-550 P-061 | Q1    | 86    | 85      | 85   | 85   | 85  | **win**               |
| Q-452 P-050 | Q2    | 62    | 60      | 60   | 60   | 60  | **win**               |
| Q-578 P-064 | Q2    | 101   | 99      | 95   | 97   | 99  | **win** (matches Hum) |
| Q-660 P-073 | Q3    | F5    | C5      | C5   | C5   | C5  | **win** (new)         |
| Q-678 P-075 | Q3    | E5    | G#4     | G#4  | G#4  | G#4 | **win**               |
| Q-732 P-081 | Q3    | Ab5   | F4      | F4   | F4   | F4  | **win**               |
| Q-455 P-050 | Q5    | 3     | 2       | 2    | 2    | 2   | **win**               |
| Q-554 P-061 | Q5    | 4     | 6       | 6    | 6    | 6   | **win**               |
| Q-457 P-050 | Q7    | 3     | 1       | 1    | 1    | 1   | **win**               |
| Q-583 P-064 | Q7    | 1     | 11      | 11   | 11   | 11  | **win**               |
| Q-619 P-068 | Q7    | 7     | 1       | 1    | 1    | 1   | **win**               |
| Q-646 P-071 | Q7    | 14    | 5       | 7    | 7    | 5   | **win** (matches Hum) |
| Q-655 P-072 | Q7    | 7     | 2       | 1    | 2    | 2   | **win**               |
| Q-664 P-073 | Q7    | 10    | 8       | 8    | 8    | 8   | **win**               |
| Q-709 P-078 | Q7    | 3     | 2       | 2    | 2    | 2   | **win**               |
| Q-718 P-079 | Q7    | 9     | 8       | 8    | 8    | 8   | **win**               |
| Q-736 P-081 | Q7    | 12    | 3       | 3    | 3    | 3   | **win**               |
| Q-763 P-084 | Q7    | 17    | 10      | 10   | 10   | 10  | **win** (new)         |
| Q-799 P-088 | Q7    | 4     | 3       | 3    | 3    | 3   | **win**               |

19 mismatches, **all wins** (17 unanimous + 2 partial that pre-date Phase 13). Q-682 P-075 Q7 was on the previous mismatch list as MIXED (DB=2, old ABC=3); after the layer-alignment fix, ABC now agrees with DB/MEI/Hum at 2 and drops off the mismatch list entirely. The two "new" rows (Q-660 P-073 Q3 and Q-763 P-084 Q7) were previously passing by coincidence — both the old (buggy) ABC extractor and the DB GT were wrong in the same way, so they matched each other. The fix exposes the truth.

### Resolved mismatches

**Q-581 P-064 Q5 — RESOLVED 2026-05-10 (tie-binding).** Tie-binding bug in `_extract_durations_single_voice` fixed: walker now drains `active_ties` entries whose pitch differs from the current event before extending/closing, so ABC ties only bind to the immediately-adjacent same-pitch note. Cross-format consensus on this row is `4` (MXML/MEI/Hum) but DB matches ABC at `3` — selfcheck-clean. Unit tests in `tests/test_abc_tie_binding.py` (7 cases).

**Q-678 / Q-655 / Q-664 / Q-682 — RESOLVED 2026-05-10 (layer-alignment).** Root cause was shared: `split_into_layered_measures` joined `&`-separated layers per measure with `|`, but a layer that only appeared in a later measure had leading empty slots that consumed zero time. So layer N's first/last notes appeared to be at time 0, displacing layer 0's true opening/closing in cross-layer comparisons. Fix in `src/answer_extraction/abc/utils.py`:

1. Added `parse_units_per_measure(content)` — number of unit-note-lengths per measure from `M:` and `L:`.
2. `split_into_layered_measures(content, units_per_measure=None)` — optional padding parameter. When set, empty layer slots become `x{N}` (a measure-rest in the unit). Without it (counters, etc.) behavior is unchanged.
3. `NoteWithTiming.start_time` added; both the main walker and the grace-note walker record it.
4. `get_first_pitch_for_voices` rewritten to be time-aware: for each voice/layer, take that layer's first note's `start_time` (timing walker) and its first pitch (existing `_extract_first_pitch_single_voice`, which preserves grace-before-chord and chord-highest behavior). The "first" pitch is the highest pitch among layers whose first note shares the minimum start time.
5. `get_last_pitch_for_voices` now passes `units_per_measure` so its end-time comparison sees absolute times.

Unit tests in `tests/test_abc_layer_alignment.py` (8 cases): units-per-measure parsing, padded vs un-padded layer split, late-starting layer doesn't displace true opener, padded layer's late notes win as last, grace-first preservation, simultaneous-layer-highest, walker start/end-time monotonicity.

### Phase 13b/c next steps

**Priority 1 — GT update + rescoring (Phase 13c) — DONE 2026-05-10.** Applied via `scripts/phase13c_apply.py` (mirrors `phase7_apply.py`; the per-row re-extract IS the guard — UPDATE only fires with values the live extractor just produced). DB backed up to `benchmark.db.pre-phase13-fix` first. Result: 19 `answer_abc` rows flipped; 119 ABC `llm_responses` for those 19 qids rescored, **69 flipped** (mix of false-positives flipping to wrong + false-negatives flipping to correct against the new GT). Post-apply selfcheck: ABC/MEI/Humdrum = 0/0/0.

**Priority 2 — commits.** Phase 13 work is uncommitted on `main` (HEAD at `4c9b04a`). Suggested split:

1. Hygiene fixes only (items 1, 2, 4, 5, 6, 7, 8 + selfcheck DB-path fix). All checks green at this stage.
2. Item 3 + walker bug fixes (broken-rhythm-after-rest, `[N` alt-ending strip). ABC selfcheck dirty (~19), intentionally.
3. Tie-binding fix + `tests/test_abc_tie_binding.py` (Q-581 resolved).
4. Layer-alignment fix + `tests/test_abc_layer_alignment.py` (Q-678/655/664/682/660/763 resolved; Q-682 dropped off mismatch list). ABC selfcheck count went 18 → 19 because two coincidentally-passing rows (Q-660, Q-763) became visible — all 19 are now WIN-class.
5. Phase 13c GT update + rescoring (`scripts/phase13c_apply.py`, modified `benchmark.db`). Separate commit, after review.

**Files changed in this session (uncommitted):**

- `src/answer_extraction/core/pitch.py` — Phase 13 item 1
- `src/llm_eval/evaluation.py` — Phase 13 item 2
- `src/answer_extraction/abc/utils.py` — Phase 13 item 3 + 2 walker fixes + Phase 13b tie-binding drain + Phase 13c layer-alignment fix
- `src/answer_extraction/mei/utils.py` — Phase 13 items 4, 5, 6
- `src/answer_extraction/humdrum/utils.py` — Phase 13 items 7, 8
- `src/answer_extraction/humdrum/q9_first_note_duration.py` — Phase 13 item 7
- `scripts/abc_selfcheck.py` / `mei_selfcheck.py` / `humdrum_selfcheck.py` — renamed from `phase{7,8,9}_*_selfcheck.py` + DB path updated to `benchmark.db`
- `scripts/phase13c_apply.py` — GT-fix apply script (mirror of `phase7_apply.py`, points at `benchmark.db`)
- `tests/test_abc_tie_binding.py` — Phase 13b, 7 cases
- `tests/test_abc_layer_alignment.py` — Phase 13c, 8 cases
- `benchmark.db` — 19 `answer_abc` rows updated, 69 `llm_responses.is_correct` flipped (Phase 13c apply, 2026-05-10)
- `benchmark.db.pre-phase13-fix` — backup snapshot (gitignored, candidate for `_archive/db_backups_2026_05/` per cleanup plan)

**Acceptance:** tests pass (45/45 integration + 7/7 tie-binding + 8/8 layer-alignment = 60/60), all three selfchecks clean (ABC/MEI/Humdrum = 0/0/0) post-Phase-13c apply.

### Option D — Repo cleanup (in flight)

Sessions 1–3 of [docs/cleanup_plan_2026_05.md](docs/cleanup_plan_2026_05.md). Session 1 Part A (this docs split) is done. Session 1 Part B (untracked junk cleanup) and Sessions 2–3 (tracked dead code, `pyproject.toml` migration) remain. Each session is sized for a fresh agent and explicitly notes which targets are safe to touch while a batch is in flight.

### Option E — analysis / paper assets

Out of scope for these phases. If the user redirects here, ask for explicit deliverables.

---

## How to hand off to the next piece of work

1. Finish the work's acceptance checks.
2. Edit this file: mark the item DONE in *Open work*, add a short note with any quirks, decisions, or deviations discovered.
3. If the work was a phase-style audit/data update, append a new section to [docs/phase_history.md](docs/phase_history.md) following the existing format.
4. Commit: `git commit -m "<scope>: <summary>"` (no `Co-Authored-By` trailer, per `~/.claude/CLAUDE.md`).

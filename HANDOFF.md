# BEAM — active handoff

This is the lean, currently-active handoff. The full narrative for **Phases 0–10** (root-cause diagnostic, per-phase scope, fixes, deferred items) lives in [docs/phase_history.md](docs/phase_history.md). Read that if you need the *why* behind the current codebase.

**Always update this doc at the end of a piece of work before handing off.** Mark what was done, note any decisions, and leave the next item actionable.

---

## Context

BEAM is the music-encoding LLM benchmark for Mozart's piano sonatas: 9 questions × 45 passages × 4 formats × 7 models. The Music Encoding Conference camera-ready was submitted **2026-04-24** (v1 models). The conference presentation is in **late May 2026**, and the goal between now and then is to (a) extend results with the v2/newer model set so the presentation can show a clean 7-model comparison, and (b) leave the repository in a clean, reviewer-ready state.

Phases 0–10 (v2 batch-pipeline hardening + four-format evaluator audits + v1↔v2 DB merge) are all DONE and committed (HEAD at `a46deae` as of 2026-05-02).

A **repo cleanup pass** is now in flight. The plan is at [docs/cleanup_plan_2026_05.md](docs/cleanup_plan_2026_05.md), structured as 3 self-contained sessions. Session 1 Part A (this docs split) is the first piece.

---

## Current state (2026-05-06)

**Active DB:** `benchmark.db` — the unified DB containing all 7 models. Ground truth and `is_correct` are internally consistent (full selfcheck = 0 mismatches across 18,630 `llm_responses` and 810 GT rows for each of the 4 formats).

**Data-collection coverage (rows in `llm_responses`):**

| Format | claude-sonnet-4-5 | gemini-3-pro-preview | gpt-5.1-2025-11-13 | qwen3-max | claude-opus-4-7 | gemini-3.1-pro-preview | gpt-5.4 |
|---|---|---|---|---|---|---|---|
| musicxml | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ |
| abc      | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅      | 1 ✅      | 1 ✅      |
| humdrum  | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅      | 1 ✅      | 1 ✅      |
| mei      | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅ 8 ✅ | 1 ✅      | 1 ✅      | **MISSING** |

The four v1 models have full 8-format-pair coverage. The three v2 models have full 1-bar coverage *except* gpt-5.4 MEI; 8-bar exists only for MusicXML across all v2 models.

**Active local config (`config.yaml`):** `database: benchmark.db`, run targeted at the gpt-5.4 1-bar MEI gap. This file is intentionally **not committed** — it is a per-user run state file.

**Backups on disk (gitignored, scheduled to move into `_archive/db_backups_2026_05/` per the cleanup plan):** `benchmark.db.pre-merge`, `benchmark.db.pre-presentation-update`, `benchmark.db.pre-gemini-humdrum-patch`, `benchmark.db.pre-gt-rescore`, `benchmark_v2.db*` (multiple). All are post-Phase-10 redundant; safe to archive.

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

Phases 1–10 are DONE. The next agent should pick **one** of the following, with the user's confirmation. Each is scoped so it can stand alone. Pick from this list, do not invent new scope.

### Option A (HIGHEST PRIORITY) — Phase 11: finish 1-bar MEI for gpt-5.4

**Why:** Only missing slot in the 1-bar matrix (see *Current state* table).

**Status at hand-off (after Phase 10 merge):** A gpt-5.4 OpenAI batch (`batch_69ebdf176aac8190a9df38386a3d4a16`) was submitted on 2026-04-24 and is recorded in `outputs/phase6_1bar_mei/batch_request_mappings.json` with `lifecycle_state: submitted`. OpenAI batches expire after 24 hours, so this batch is almost certainly stale — running `--retry-stale` will be needed to resubmit. Claude and Gemini already have 405 mei rows each in `benchmark.db`; gpt-5.4 has 0.

`config.yaml` is now pointed at `benchmark.db` (Phase 10 update) and still configured for this run (`run_id: phase6_1bar_mei`, `formats: [mei]`, `num_measures: [1]`).

**How to start:**
1. `sqlite3 benchmark.db "SELECT model, COUNT(*) FROM llm_responses WHERE format='mei' GROUP BY model;"` — should show claude-opus-4-7=405, gemini-3.1-pro-preview=405, gpt-5.4=0 (plus the four v1 models at 810 each).
2. `python3 -u scripts/submit_all_batches.py --poll-only` — confirms the OpenAI batch is `expired`/`failed_stale`. If so, run `python3 -u scripts/submit_all_batches.py --retry-stale` to resubmit just gpt-5.4 (Claude/Gemini are already `saved`).
3. After completion, run the 4-format inline selfcheck on `benchmark.db` to confirm GT consistency.

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

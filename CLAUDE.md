# BEAM — Claude Code working notes

BEAM is the Music Encoding Benchmark: it scores LLMs on 9 questions × 45 passages × 4 encoding formats (ABC, Humdrum, MEI, MusicXML) over Mozart's piano sonatas. Conference camera-ready was submitted 2026-04-24 (v1 models); current work is the late-May 2026 presentation update extending coverage to v2/reasoning models.

For deeper context read [README.md](README.md) (project overview) and [HANDOFF.md](HANDOFF.md) (running log of in-flight work and decisions). Update HANDOFF.md periodically as work progresses so the next session can pick up cold — its exact structure changes over time, so match whatever shape it has when you read it.

## Active database

- **`benchmark.db`** is the single unified DB (post-2026-05-02 merge) containing all 7 models. Use this one.
- `benchmark_v2.db` and any `*.db.pre-*` / `*.merged-into-v1` files in the repo root are backups or stale; do not write to them. They are gitignored.
- Ground truth lives in `questions.answer_{format}` columns. LLM responses go in `llm_responses`.

## Common commands

```bash
# Direct (non-batch) run — uses config.yaml
python src/cli/run_benchmark.py

# Batch API submission (parallel across all enabled providers, resumable)
python scripts/submit_all_batches.py
python scripts/submit_all_batches.py --poll-only          # resume an in-flight run
python scripts/submit_all_batches.py --retry-stale         # re-submit failed_stale batches

# Passage-chunked submission for OpenAI gpt-5.4's 1.35M enqueued-token cap
python scripts/submit_chunked.py --chunk-size 5

# Daemonize a long-running batch job (multi-hour polls survive terminal disconnects)
scripts/daemon_launch.sh outputs/runlog.log python scripts/submit_all_batches.py

# Tests
python -m pytest tests/test_all_extractors.py -v
python -m pytest tests/test_all_extractors.py -k "humdrum and Q5"
```

## config.yaml is per-user run state

`config.yaml` is intentionally modified-but-uncommitted. It carries the active `run_id`, `formats`, `num_measures`, `passages`, and which providers are enabled. **Don't commit it** unless we're explicitly resetting the default.

`submit_all_batches.py --poll-only` resumes from `BatchRequestStorage`, but the script still reads `config.yaml` to rebuild expected test cases. If `formats` or `num_measures` don't match the original submission, results are silently discarded. Verify config matches before resuming.

## Project rules

- **No fallbacks.** If an API key, model, or input is wrong, raise — don't silently switch to a default. (Example: `pitch_to_midi` returning MIDI 0 on parse failure is a documented violation, not a pattern to copy.)
- **No backwards-compat shims.** Delete dead paths cleanly; we are not supporting old DB schemas or removed providers.
- **No emojis** in code, commits, or docs.
- **Minimal comments** — only where the *why* is non-obvious.
- **Tiny dry run before declaring data-collection work done** — 5 requests, one provider, end-to-end. The pipeline has bitten us before with silent alignment bugs.

## Extractors (`src/answer_extraction/`)

Four parallel implementations (`abc/`, `humdrum/`, `mei/`, `musicxml/`), each with `q1_*.py` … `q9_*.py` and a format-specific `utils.py`. They share `core/pitch.py` and `core/duration.py`. When a question type exists in all four formats, the four files should look like siblings — same shape, same naming, same docstring contract. Cross-format divergence in extractor output usually means a bug, not a real encoding difference.

The `@register_extractor(question_id, "format")` decorator wires extractors into `registry.py`. New extractors must also be imported from the format's `__init__.py`.

## Throwaway phase scripts

Scripts named `phase{N}_probes*.py`, `phase{N}_impact.py`, `phase{N}_suspect_detail.py`, `phase{N}_verify_fix.py`, `phase{N}_cross_format_diff.py` are one-shot debugging tools tied to a particular round of work. They are intentionally untracked and get deleted when their round lands. Don't generalize them or commit them.

The exception is `phase{N}_apply.py` (DB-update + rescoring scripts) and `phase{N}_*_selfcheck.py` (self-consistency sweeps) — these are tracked because they document the data fixes.

## API keys (`.env`)

The `.env` file (gitignored) must use these exact names — the code does not fall back to alternates:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY` (not `CLAUDE_API_KEY`)
- `GOOGLE_API_KEY` (not `GEMINI_API_KEY` — the fallback was removed deliberately)
- `DASHSCOPE_API_KEY` (Alibaba/Qwen, OpenAI-compatible endpoint)

## Reasoning-model gotchas

- **gpt-5.4 (OpenAI Responses API):** 1.35M enqueued-token org-wide cap forces passage-chunked submission for verbose formats (especially MEI). Use `scripts/submit_chunked.py`. `max_tokens` must be ≤ 65536 for batch (cap is 128000 but 65536 avoids edge cases). Sending `temperature` with reasoning models is silently dropped (OpenAI) or returns 400 (Anthropic) — the batch code already handles this.
- **claude-opus-4-7:** streaming + `extra_body` required; 128k token cap on output.
- **gemini-3.1-pro-preview:** must use file-based JSONL batch (not inline) so the `key` field round-trips and per-request alignment survives. Tier 1 is 250 RPD, project-wide — a new key in the same GCP project does *not* lift it.

## Batch resumability

`BatchRequestStorage` (`outputs/{run_id}/batch_request_mappings.json`) is the single source of truth for in-flight batches. Lifecycle states: `submitted → downloaded → saved`, plus `failed_stale` for expired/not-found batches. Atomic tmp+replace writes. Don't bypass it by reading provider state directly.

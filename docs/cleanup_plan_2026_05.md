# BEAM repo cleanup & refactor plan

## Context

BEAM is a research codebase: 9 questions × 45 passages × 4 formats × 7 LLMs over Mozart's piano sonatas. Camera-ready was submitted 2026-04-24; presentation update lands late May 2026. Phases 0–10 of the v2 redesign + evaluator audits are DONE — `benchmark.db` is the unified DB. The codebase itself is solid (`src/cli/`, `src/core/`, `src/answer_extraction/`, `src/llm_eval/` are all live). What's messy is the **periphery**: ten DB backup files at the repo root, eight untracked throwaway phase-debug scripts, three empty `src/` subdirectories, an entire dead `src/scripts/` tree (829 lines never imported), a 52 MB `legacy_outputs/`, and a `paper/` directory of conference Word docs that's tracked despite being in `.gitignore`.

Per user direction:

- **Move to `_archive/`, don't delete.** `_archive/` is gitignored, so moving tracked files there removes them from git tracking while keeping them on disk.
- **An OpenAI batch is in flight.** Do not touch `benchmark.db`, `config.yaml`, `outputs/`, `scripts/submit_all_batches.py`, `scripts/submit_chunked.py`, or any module the running daemon might import (`src/llm_eval/*`, `src/core/*`, `src/answer_extraction/*`). Defer anything risky (the editable-install / `pip install -e .` re-install in Session 3) until the batch has finished.
- Archive both `src/scripts/` and `paper/`; migrate `setup.py` → `pyproject.toml` + `ruff`; leave `outputs/` and `CLAUDE.md` alone.

User wants the work split so each session can be completed cleanly before context is reset for the next. Plan is divided into **3 sessions**, sized so each one is a fresh-agent unit of work.

---

## Audit findings (concise)

| Category | Count / Size | Status | Action |
|---|---|---|---|
| Root `*.db.pre-*` / `*.merged-into-v1` / empty `benchmark_v2.db` | 11 files, ~25 MB | untracked, gitignored | move to `_archive/db_backups_2026_05/` |
| `BEAM_camera_ready.pdf` | 1 file, 236 KB | untracked, gitignored | move to `_archive/` |
| `legacy_outputs/` | 56 dirs, 52 MB | untracked, gitignored | move whole dir to `_archive/legacy_outputs/` |
| `_backup/` | 2 scripts | untracked, gitignored | move whole dir to `_archive/_backup/` |
| Throwaway phase debug scripts in `scripts/` | 8 files | untracked | move to `_archive/phase_scripts_throwaway/` |
| `src/scripts/` | 7 files, 829 lines | **tracked**, never imported | `git rm -r` + move to `_archive/dead_src/scripts/` |
| `paper/` | 4 Word/Excel docs | **tracked**, gitignored (pre-existing) | `git rm -r` + move to `_archive/paper/` |
| `src/parsers/`, `src/pipeline/`, `src/ground_truth/` | 3 empty dirs | only `__pycache__/` (gitignored) | `rm -rf` (empty husks) |
| `setup.py` | 54 lines | tracked | replace with `pyproject.toml`; archive `setup.py` |

`outputs/` and `CLAUDE.md` left alone.

---

## Where this plan lives

Once Session 1 starts, the plan is copied into the repo at `docs/cleanup_plan_2026_05.md` (mirrors the existing `docs/presentation_plan_2026_05.md` naming). The original at `~/.claude/plans/please-read-about-this-piped-toast.md` is Claude Code's local working scratch and is consumed once execution finishes.

## Session boundaries (read this first)

| Session | Risk to in-flight batch | Touches git index? | Suggested timing |
|---|---|---|---|
| **Session 1** — docs reorganization + untracked-only cleanup | None (docs edits + moves of untracked files; zero runtime impact) | Yes (1 commit for docs) | Anytime, even with daemon running |
| **Session 2** — tracked dead code | Low (touches files daemon never imports) | Yes (2 commits) | Anytime safe; quick batch-status check before starting |
| **Session 3** — `pyproject.toml` migration | Moderate (`pip install -e .` re-installs the package) | Yes (1 commit) | **Wait until batch is finished** |

Each session ends with a `git status` and the working tree in a clean state, so a new session can pick up cold.

---

## SESSION 1 — Docs reorganization + untracked junk cleanup

**Preconditions**

- Anytime is fine (does not touch the DB, `outputs/`, or `config.yaml`).
- Confirm starting state: `git status --porcelain` should match the current snapshot (modified `config.yaml`, `scripts/daemon_launch.sh`; untracked phase scripts; `CLAUDE.md` untracked; etc.). If extra modifications exist, stop and reconcile first.

**Part A — Documentation split**

The current `HANDOFF.md` (582 lines) is ~80% historical phase narrative (Phases 0–10) and ~20% active state. Post-Phase-10 + post-camera-ready is a natural seam to split.

1. Save this plan into the repo so it's tracked alongside the rest of the work:

   ```bash
   cp ~/.claude/plans/please-read-about-this-piped-toast.md docs/cleanup_plan_2026_05.md
   ```

2. Split `HANDOFF.md`:
   - Read current HANDOFF.md end-to-end (it's 582 lines; pull all of it).
   - Create [docs/phase_history.md](../../Documents/Main/School/MasterDegree/GitHub/BEAM/docs/phase_history.md) containing the Phase 0–10 narrative section (everything from `## Phases` through the end of `### Phase 10 — Merge benchmark_v2.db into benchmark.db (DONE, 2026-05-02)`). Add a one-line preamble: "Historical phase log for BEAM v2 hardening work, Phases 0–10 (2026-04-19 → 2026-05-02). Active handoff state lives in [/HANDOFF.md](../HANDOFF.md)."
   - Rewrite `HANDOFF.md` as a lean active handoff (~50–80 lines):
     - Context (3–4 sentences: what BEAM is, what was just completed, what's next)
     - Current state table (the eval matrix from the existing HANDOFF, kept current)
     - Open work for the next agent (the existing Options A / B / C / D section, copied verbatim from the current HANDOFF lines ~526–574)
     - "How to hand off" instructions (copied from existing lines ~577–582)
     - A pointer line: "Phase history (0–10) lives at [docs/phase_history.md](docs/phase_history.md)."
   - The new HANDOFF should not contain phase narrative; if a reader needs the *why*, they follow the pointer.

3. Verify CLAUDE.md still aligns. The current line is "For deeper context read [README.md](README.md) (project overview) and [HANDOFF.md](HANDOFF.md) (running log of in-flight work and decisions)." — that's still accurate after the split. No edit needed unless the user wants to reference `phase_history.md` directly.

4. Stage and commit:

   ```bash
   git add HANDOFF.md docs/phase_history.md docs/cleanup_plan_2026_05.md
   git commit -m "docs: split HANDOFF into active state + phase history; add cleanup plan"
   ```

**Part B — Untracked junk cleanup**

1. Baseline snapshot:

   ```bash
   cp benchmark.db benchmark.db.pre-cleanup-snapshot   # gitignored as *.db
   git rev-parse HEAD                                  # record SHA for rollback
   ```

2. Set up archive substructure:

   ```bash
   mkdir -p _archive/db_backups_2026_05
   mkdir -p _archive/phase_scripts_throwaway
   mkdir -p _archive/dead_src
   mkdir -p _archive/setup_py_legacy
   ```

3. Move 11 untracked DB backups to `_archive/db_backups_2026_05/`:

   ```bash
   mv benchmark.db.pre-gemini-humdrum-patch _archive/db_backups_2026_05/
   mv benchmark.db.pre-gt-rescore           _archive/db_backups_2026_05/
   mv benchmark.db.pre-merge                _archive/db_backups_2026_05/
   mv benchmark.db.pre-presentation-update  _archive/db_backups_2026_05/
   mv benchmark_v2.db                       _archive/db_backups_2026_05/
   mv benchmark_v2.db.merged-into-v1        _archive/db_backups_2026_05/
   mv benchmark_v2.db.pre-merge             _archive/db_backups_2026_05/
   mv benchmark_v2.db.pre-phase6-fix        _archive/db_backups_2026_05/
   mv benchmark_v2.db.pre-phase7-fix        _archive/db_backups_2026_05/
   mv benchmark_v2.db.pre-phase8-fix        _archive/db_backups_2026_05/
   mv benchmark_v2.db.pre-phase9-fix        _archive/db_backups_2026_05/
   ```

4. Move other untracked top-level junk:

   ```bash
   mv legacy_outputs        _archive/legacy_outputs
   mv _backup               _archive/_backup
   mv BEAM_camera_ready.pdf _archive/BEAM_camera_ready.pdf
   ```

5. Move 8 throwaway phase debug scripts:

   ```bash
   mv scripts/phase7_impact.py            _archive/phase_scripts_throwaway/
   mv scripts/phase7_probes.py            _archive/phase_scripts_throwaway/
   mv scripts/phase7_probes2.py           _archive/phase_scripts_throwaway/
   mv scripts/phase9_cross_format_diff.py _archive/phase_scripts_throwaway/
   mv scripts/phase9_probes.py            _archive/phase_scripts_throwaway/
   mv scripts/phase9_probes2.py           _archive/phase_scripts_throwaway/
   mv scripts/phase9_suspect_detail.py    _archive/phase_scripts_throwaway/
   mv scripts/phase9_verify_fix.py        _archive/phase_scripts_throwaway/
   ```

**Verification**

```bash
ls *.db                                           # only benchmark.db (+ snapshot)
ls _archive/db_backups_2026_05/ | wc -l           # 11
du -sh _archive/legacy_outputs                    # ~52M
ls _archive/_backup/                              # 2 scripts
ls _archive/phase_scripts_throwaway/ | wc -l      # 8
ls scripts/phase*.py                              # only 7 tracked: phase7_apply, phase7_abc_selfcheck,
                                                  #   phase8_apply, phase8_mei_selfcheck,
                                                  #   phase9_apply, phase9_humdrum_selfcheck, phase10_merge
git status                                        # untracked list shrunk to: CLAUDE.md, docs/presentation_plan_2026_05.md,
                                                  #   scripts/submit_chunked.py (and benchmark.db.pre-cleanup-snapshot)
```

**No commits this session.** All moved content was untracked.

**Hand-off note for Session 2**: working tree shape, the SHA recorded in step 1, and any deviations from the verification expectations.

---

## SESSION 2 — Tracked dead code removal

**Preconditions**

- Run `ps aux | grep submit_all_batches | grep -v grep` and `tail -n 20 outputs/*/runlog.log` (or wherever the daemon log lives — check [scripts/daemon_launch.sh](../../Documents/Main/School/MasterDegree/GitHub/BEAM/scripts/daemon_launch.sh) for the log path). If a daemon is actively polling, that's still fine for this session — none of the targets are imported by the runtime — but **don't run pytest while the daemon writes to `benchmark.db`** (concurrent SQLite writes from a separate process can lock). If the daemon is active, skip the test step at the end and instead defer it to the next safe window.
- Session 1 must be complete (`_archive/dead_src/` exists; the throwaway phase scripts are gone from `scripts/`).

**Steps**

1. Pre-flight import check (must return zero results):

   ```bash
   grep -rE "from src\.scripts|import src\.scripts|src/scripts" \
     --include='*.py' src/ scripts/ tests/
   ```

   If anything matches, **stop** and report — this plan assumes no live references.

2. Archive `src/scripts/` (preserves content, removes tracking):

   ```bash
   mv src/scripts _archive/dead_src/scripts   # removes from working tree at original path
   git add -A src/scripts                     # stages the deletion (path no longer exists)
   ```

3. Archive `paper/`:

   ```bash
   mv paper _archive/paper
   git add -A paper                           # stages 4 deletions
   ```

4. Remove empty `src/` subdirectories. Pre-flight (must return zero output for both):

   ```bash
   find src/parsers src/pipeline src/ground_truth -type f ! -path "*/__pycache__/*"
   git ls-files src/parsers src/pipeline src/ground_truth
   ```

   If both empty:

   ```bash
   rm -rf src/parsers src/pipeline src/ground_truth
   ```

5. Verify imports still work (no DB writes):

   ```bash
   python -c "from src.llm_eval import BenchmarkRunner, BenchmarkConfig; print('llm_eval ok')"
   python -c "from src.answer_extraction import registry; print('extractors ok')"
   python -c "from src.core import db_utils, extract_passage; print('core ok')"
   ```

6. Run the test suite **only if no daemon is writing to `benchmark.db`**:

   ```bash
   python -m pytest tests/test_all_extractors.py -v   # 45 tests, read-only against benchmark.db
   ```

   If the daemon is active, skip and note "tests deferred".

7. Commit, in two atomic commits:

   ```bash
   git add -A src/scripts
   git commit -m "refactor: archive unused src/scripts/ tree (never imported)"

   git add -A paper
   git commit -m "chore: archive paper drafts (already in .gitignore)"
   ```

   No `Co-Authored-By` trailer (per `~/.claude/CLAUDE.md`).

**Verification**

```bash
ls src/                                  # cli/  core/  answer_extraction/  llm_eval/  __init__.py  README.md  __pycache__
ls _archive/dead_src/scripts/            # database/  data_import/  utilities/  __init__.py  README.md
ls _archive/paper/                       # 4 docx/xlsx files
git log --oneline -3                     # 2 new commits on top of a46deae
git status                               # only modified config.yaml, scripts/daemon_launch.sh; untracked CLAUDE.md etc.
```

**Hand-off note for Session 3**: confirm the two commits landed cleanly; record the new HEAD SHA. Confirm whether the in-flight batch has finished — Session 3 should not start until it has.

---

## SESSION 3 — `pyproject.toml` + ruff migration

**Preconditions**

- **In-flight OpenAI batch must be finished.** Confirm via `python scripts/submit_all_batches.py --poll-only` (which reports completed/failed counts from `BatchRequestStorage`) or by inspecting `outputs/<run_id>/batch_request_mappings.json` for `lifecycle_state: saved` on every entry.
- The daemon process must not be running (`ps aux | grep submit | grep -v grep`).
- Session 2 must be complete (`src/scripts/` and `paper/` archived; commits landed).

**Why wait**: this session runs `pip install -e .[dev]` which re-installs the editable package. If the running daemon has the old install loaded, the re-install can confuse module resolution mid-poll.

**Steps**

1. Read the current state (no edits yet):
   - [setup.py](../../Documents/Main/School/MasterDegree/GitHub/BEAM/setup.py) — current entry points: `run-benchmark`, `add-question`, `review-passage`, `init-database`. Note that `init-database` points at `src/scripts/database/init_database.py`, which was archived in Session 2 — that entry point will be dropped.
   - [requirements.txt](../../Documents/Main/School/MasterDegree/GitHub/BEAM/requirements.txt) — runtime deps to mirror in `pyproject.toml`'s `[project] dependencies`.
   - [README.md](../../Documents/Main/School/MasterDegree/GitHub/BEAM/README.md) — currently references `python src/scripts/database/init_database.py` and `python src/scripts/database/export_database.py` (lines 34–37). Both targets are now in `_archive/dead_src/scripts/database/`. Update README to either point at the archive path or note that DB initialization is no longer part of the user-facing flow (the DB ships with the repo).
   - Confirm `src/cli/review_passage.py` actually exists before keeping the `review-passage` entry point — `setup.py` references it but the audit didn't enumerate `src/cli/`. If missing, drop it.

2. Write [pyproject.toml](../../Documents/Main/School/MasterDegree/GitHub/BEAM/pyproject.toml):

   ```toml
   [build-system]
   requires = ["setuptools>=68", "wheel"]
   build-backend = "setuptools.build_meta"

   [project]
   name = "beam"
   version = "0.2.0"
   description = "Music Encoding Benchmark — LLM evaluation across ABC, Humdrum, MEI, MusicXML"
   readme = "README.md"
   requires-python = ">=3.10,<3.13"
   authors = [{name = "Liam Pond", email = "liam.pond@mail.mcgill.ca"}]
   dependencies = [
     # mirror requirements.txt verbatim — copy from the file at migration time
   ]

   [project.optional-dependencies]
   dev = ["pytest>=7", "ruff>=0.4"]

   [project.scripts]
   run-benchmark  = "src.cli.run_benchmark:main"
   add-question   = "src.cli.add_question:main"
   review-passage = "src.cli.review_passage:main"   # only if file exists; otherwise drop

   [tool.setuptools.packages.find]
   where = ["."]
   include = ["src*"]

   [tool.pytest.ini_options]
   testpaths = ["tests"]

   [tool.ruff]
   line-length = 100
   target-version = "py310"

   [tool.ruff.lint]
   select = ["E", "F", "I"]
   ```

3. Archive `setup.py`:

   ```bash
   mv setup.py _archive/setup_py_legacy/setup.py
   git add -A setup.py pyproject.toml
   ```

4. Update `README.md`:
   - Strip the `python src/scripts/database/init_database.py` and `export_database.py` lines from the Quick Start (or move them to a "rebuilding the database" subsection that points to `_archive/dead_src/scripts/database/`).
   - Add a `pip install -e ".[dev]"` line in the Installation section for contributors.

5. Verify the new install works:

   ```bash
   pip install -e ".[dev]"                 # installs cleanly; expect no errors
   python -m pytest tests/ -v              # 45 tests pass
   ruff check src/ scripts/                # baseline run; treat existing warnings as informational
   python src/cli/run_benchmark.py --help  # CLI entry point still imports
   ```

6. Commit:

   ```bash
   git add -A README.md pyproject.toml setup.py
   git commit -m "build: migrate setup.py to pyproject.toml; add ruff dev tooling"
   ```

7. Final cleanup — once everything passes:

   ```bash
   rm benchmark.db.pre-cleanup-snapshot
   ```

**Verification**

```bash
ls *.db                                 # only benchmark.db
ls -la setup.py 2>/dev/null              # no such file
ls pyproject.toml                        # exists
git log --oneline -1                     # the migration commit on top of Session 2's 2 commits
git status                               # only modified config.yaml; untracked CLAUDE.md, presentation_plan, submit_chunked.py
du -sh _archive/                         # ~80M+
```

**End state**: 3 commits on top of `a46deae` (the Phase 10 unified-DB commit). Repo root has only the live files (README, HANDOFF, CLAUDE, config.yaml, requirements.txt, pyproject.toml, .gitignore, .env.example, benchmark.db). `src/` has only the four live subpackages. `scripts/` has only operational + tracked phase scripts.

---

## Summary of commits across all sessions

1. (Session 1) `docs: split HANDOFF into active state + phase history; add cleanup plan`
2. (Session 2) `refactor: archive unused src/scripts/ tree (never imported)`
3. (Session 2) `chore: archive paper drafts (already in .gitignore)`
4. (Session 3) `build: migrate setup.py to pyproject.toml; add ruff dev tooling`

No `Co-Authored-By` trailers (per `~/.claude/CLAUDE.md`).

---

## Critical files (reference)

| Purpose | Path |
|---|---|
| Audit source-of-truth | [HANDOFF.md](../../Documents/Main/School/MasterDegree/GitHub/BEAM/HANDOFF.md) |
| Existing cleanup proposal | [docs/presentation_plan_2026_05.md](../../Documents/Main/School/MasterDegree/GitHub/BEAM/docs/presentation_plan_2026_05.md) |
| Working rules | [CLAUDE.md](../../Documents/Main/School/MasterDegree/GitHub/BEAM/CLAUDE.md) |
| Current build metadata | [setup.py](../../Documents/Main/School/MasterDegree/GitHub/BEAM/setup.py) |
| Runtime deps | [requirements.txt](../../Documents/Main/School/MasterDegree/GitHub/BEAM/requirements.txt) |
| README to update | [README.md](../../Documents/Main/School/MasterDegree/GitHub/BEAM/README.md) |
| Daemon launcher (find log path here) | [scripts/daemon_launch.sh](../../Documents/Main/School/MasterDegree/GitHub/BEAM/scripts/daemon_launch.sh) |
| Batch state path (do NOT touch) | [outputs/](../../Documents/Main/School/MasterDegree/GitHub/BEAM/outputs/) |
| Active DB (do NOT touch) | [benchmark.db](../../Documents/Main/School/MasterDegree/GitHub/BEAM/benchmark.db) |

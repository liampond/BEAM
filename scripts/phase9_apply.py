"""Phase 9: apply humdrum GT updates from extractor fixes.

Run with --apply to persist; default is dry-run.

Two fixes drive these updates:
1. ``is_rest`` now treats any token containing 'r' as a rest. Pitch letters
   following 'r' (e.g. ``8rBB``, ``8rc``, ``8rg``) are rest-position hints,
   not pitches.
2. Q3 (first pitch upper staff) now uses row-grouped extraction so that
   spine splits at the start of the passage are handled — the highest
   pitch among simultaneous notes across sub-spines wins.

Affected GT rows are all in 8-bar passages (P-050, P-081, P-084, P-089).
No humdrum llm_responses exist for 8-bar questions, so no rescoring is
required.
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.answer_extraction.humdrum  # noqa
from src.answer_extraction.registry import get_extractor

DB = ROOT / "benchmark_v2.db"
PASS = ROOT / "passages" / "humdrum"

# (question_id, passage_id, qtype, expected_old_humdrum, expected_new_humdrum)
# Expected new values are computed by the fixed extractor.
ROWS = [
    ("Q-451", "P-050", 1, "48", "44"),
    ("Q-802", "P-089", 1, "56", "54"),
    ("Q-452", "P-050", 2, "62", "60"),
    ("Q-758", "P-084", 2, "179", "178"),
    ("Q-732", "P-081", 3, "Eb3", "F4"),
    ("Q-458", "P-050", 8, "28", "34"),
    ("Q-764", "P-084", 8, "19", "20"),
    ("Q-809", "P-089", 8, "11", "13"),
]

apply = "--apply" in sys.argv
mode = "APPLYING" if apply else "DRY RUN"
print(f"=== Phase 9 GT update — {mode} ===\n")

conn = sqlite3.connect(DB)
cur = conn.cursor()

actually_updated = 0
for qid, pid, qt, old_expected, new_expected in ROWS:
    cur.execute(
        "SELECT answer_humdrum FROM questions WHERE question_id=?",
        (qid,),
    )
    row = cur.fetchone()
    if row is None:
        print(f"  {qid}: NOT FOUND in DB")
        continue
    db_value = row[0]

    extractor = get_extractor(qt, "humdrum")
    computed = extractor(str(PASS / f"{pid}.krn"))

    if str(computed) != new_expected:
        print(
            f"  {qid} {pid} Q{qt}: extractor returned {computed!r}, "
            f"expected {new_expected!r} — SKIP"
        )
        continue

    if str(db_value) != old_expected:
        print(
            f"  {qid} {pid} Q{qt}: DB has {db_value!r}, expected old "
            f"{old_expected!r} — DB drift, SKIP"
        )
        continue

    print(
        f"  {qid} {pid} Q{qt}: answer_humdrum {db_value!r} -> {new_expected!r}"
    )
    if apply:
        cur.execute(
            "UPDATE questions SET answer_humdrum=? WHERE question_id=?",
            (new_expected, qid),
        )
        actually_updated += cur.rowcount

if apply:
    conn.commit()
    print(f"\nCommitted {actually_updated} row updates to {DB.name}")
else:
    print("\n(dry run — no changes written. Re-run with --apply to persist.)")

conn.close()

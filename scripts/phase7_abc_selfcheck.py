"""Phase 7 Step 1: cross-check answer_abc rows vs current extractor output.

For every (question_id, passage_id, question_type_id, answer_abc) row, run the
registered ABC extractor against passages/abc/<passage_id>.abc and report any
mismatch. A clean pass proves the DB and extractor are self-consistent.
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.answer_extraction.registry import get_extractor
import src.answer_extraction.abc  # registers extractors

DB = ROOT / "benchmark_v2.db"
PASSAGE_DIR = ROOT / "passages" / "abc"

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute(
    "SELECT question_id, passage_id, question_type_id, answer_abc FROM questions "
    "WHERE answer_abc IS NOT NULL ORDER BY question_type_id, passage_id"
)
rows = cur.fetchall()

mismatches = []
errors = []
for qid, pid, qtype, expected in rows:
    path = PASSAGE_DIR / f"{pid}.abc"
    if not path.exists():
        errors.append((qid, pid, qtype, f"MISSING FILE {path.name}"))
        continue
    extractor = get_extractor(qtype, "abc")
    if extractor is None:
        errors.append((qid, pid, qtype, "NO EXTRACTOR"))
        continue
    try:
        got = extractor(str(path))
    except Exception as e:
        errors.append((qid, pid, qtype, f"EXC {type(e).__name__}: {e}"))
        continue
    if str(got) != str(expected):
        mismatches.append((qid, pid, qtype, expected, got))

total = len(rows)
print(f"Checked {total} rows")
print(f"Mismatches: {len(mismatches)}")
print(f"Errors: {len(errors)}")
print()
by_qtype = {}
for qid, pid, qtype, exp, got in mismatches:
    by_qtype.setdefault(qtype, []).append((qid, pid, exp, got))
for qtype in sorted(by_qtype):
    print(f"--- Q{qtype}: {len(by_qtype[qtype])} mismatches ---")
    for qid, pid, exp, got in by_qtype[qtype][:15]:
        print(f"  {qid} {pid}: expected={exp!r} got={got!r}")
    if len(by_qtype[qtype]) > 15:
        print(f"  ... +{len(by_qtype[qtype]) - 15} more")
print()
if errors:
    print("--- ERRORS ---")
    for e in errors[:20]:
        print(f"  {e}")

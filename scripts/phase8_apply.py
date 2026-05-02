"""Apply Phase 8 MEI GT fixes: update answer_mei for the 5 rows whose
value changes after the rdg-exclusion and tie-chain fixes.

Usage:
  python scripts/phase8_apply.py          # dry run — print SQL but don't write
  python scripts/phase8_apply.py --apply  # actually write to DB
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.answer_extraction.registry import get_extractor
import src.answer_extraction.mei  # registers extractors

DB = ROOT / "benchmark_v2.db"
PASSAGE_DIR = ROOT / "passages" / "mei"

APPLY = "--apply" in sys.argv

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute(
    "SELECT question_id, passage_id, question_type_id, answer_mei FROM questions "
    "WHERE answer_mei IS NOT NULL ORDER BY question_type_id, passage_id"
)
rows = cur.fetchall()

updates = []
for qid, pid, qtype, expected in rows:
    path = PASSAGE_DIR / f"{pid}.mei"
    extractor = get_extractor(qtype, "mei")
    got = extractor(str(path))
    if str(got) != str(expected):
        updates.append((qid, pid, qtype, expected, str(got)))

print(f"Rows to update: {len(updates)}")
for qid, pid, qtype, old, new in updates:
    print(f"  {qid} {pid} Q{qtype}: {old!r} -> {new!r}")

if not APPLY:
    print("\nDry run. Re-run with --apply to write.")
    sys.exit(0)

for qid, pid, qtype, old, new in updates:
    cur.execute("UPDATE questions SET answer_mei = ? WHERE question_id = ?", (new, qid))
conn.commit()
print(f"\nUpdated {len(updates)} rows.")

# No llm_responses rescoring needed: no MEI responses exist yet.
cur.execute("SELECT COUNT(*) FROM llm_responses WHERE format='mei'")
count = cur.fetchone()[0]
print(f"llm_responses(format='mei') rows: {count} (no rescoring needed)")

conn.close()

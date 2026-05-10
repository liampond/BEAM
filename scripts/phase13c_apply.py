"""Phase 13c: apply ABC GT corrections to benchmark.db.

After the Phase 13 extractor fixes (layer-alignment, tie-binding, broken-rhythm
drain across rests, [N alt-ending strip), 19 ABC selfcheck mismatches remain.
All 19 are WIN-class: the new extractor agrees with the MusicXML/MEI/Humdrum
consensus, so the DB ground truth is wrong. This script flips those GTs and
rescores affected llm_responses.

Mechanism mirrors scripts/phase7_apply.py: re-extract every row with answer_abc
set, persist UPDATE wherever extractor output differs from the stored value.
The re-extract IS the guard — we never UPDATE with anything other than what the
fixed extractor just produced for the live passage file.
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.answer_extraction.registry import get_extractor
import src.answer_extraction.abc  # noqa: F401

DB = ROOT / "benchmark.db"
PASSAGE_DIR = ROOT / "passages" / "abc"


def main(apply: bool):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT question_id, passage_id, question_type_id, answer_abc "
        "FROM questions WHERE answer_abc IS NOT NULL"
    )
    rows = cur.fetchall()
    changes = []
    for qid, pid, qtype, old in rows:
        ext = get_extractor(qtype, "abc")
        new = ext(str(PASSAGE_DIR / f"{pid}.abc"))
        if str(new) != str(old):
            changes.append((qid, pid, qtype, old, new))
    print(f"{len(changes)} rows will change")
    for qid, pid, qtype, old, new in sorted(changes, key=lambda r: (r[2], r[0])):
        print(f"  {qid} ({pid}) Q{qtype}: {old!r} -> {new!r}")
    if not apply:
        print("\n(dry-run; pass --apply to persist)")
        return

    for qid, pid, qtype, old, new in changes:
        cur.execute("UPDATE questions SET answer_abc=? WHERE question_id=?", (new, qid))

    import re

    def _normalize(s: str) -> str:
        s = (s or "").strip().lower()
        s = re.sub(r"[.,;:\'\"!?]", "", s)
        s = re.sub(r"\s+", " ", s)
        return s

    def compare(extracted: str, expected: str) -> bool:
        if not extracted or not expected:
            return False
        e = _normalize(extracted)
        x = _normalize(expected)
        if e == x:
            return True
        try:
            return abs(float(e) - float(x)) < 0.01
        except ValueError:
            return False

    affected_qids = {qid for qid, _, _, _, _ in changes}
    if affected_qids:
        qs = ",".join(["?"] * len(affected_qids))
        cur.execute(
            f"SELECT id, question_id, extracted_answer, is_correct "
            f"FROM llm_responses WHERE format='abc' AND question_id IN ({qs})",
            tuple(affected_qids),
        )
        resp_rows = cur.fetchall()
        flipped = 0
        new_gt = {qid: new for qid, _, _, _, new in changes}
        for rid, qid, raw, is_correct in resp_rows:
            new_is_correct = 1 if compare(raw, new_gt[qid]) else 0
            if int(is_correct or 0) != new_is_correct:
                cur.execute(
                    "UPDATE llm_responses SET is_correct=? WHERE id=?",
                    (new_is_correct, rid),
                )
                flipped += 1
        print(f"\nRe-scored {len(resp_rows)} ABC llm_responses; {flipped} flipped")
    conn.commit()
    conn.close()
    print("\nDB updated.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)

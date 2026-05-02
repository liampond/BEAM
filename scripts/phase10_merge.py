"""Phase 10: merge benchmark_v2.db into benchmark.db.

Default target is `benchmark.db` (the v1 file that's tracked by git);
default source is `benchmark_v2.db`. The merge has three parts:

1. Adopt v2 ground-truth corrections in the target:
   - 90 Q6 question_text rows (Phase 6 enharmonic-distinct clarification)
   - 8 answer_humdrum rows (Phase 9 humdrum extractor fixes)

2. Rescore the existing v1 `llm_responses` for those 8 humdrum questions
   against the new ground truth. Q6 prompt-text changes do not trigger
   rescoring per the user's explicit decision (see HANDOFF.md Phase 10
   Option Z, "Decision (made by user 2026-05-02)").

3. Copy every row of `source.llm_responses` into the target via
   `INSERT OR IGNORE`. v1 and v2 model names are disjoint, so the
   UNIQUE(question_id, passage_id, format, model) constraint guarantees
   no in-place clobbering.

Dry-run by default. Re-runnable: every step is idempotent.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_eval.evaluation import compare_answers


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default=str(ROOT / "benchmark.db"))
    ap.add_argument("--source", default=str(ROOT / "benchmark_v2.db"))
    ap.add_argument("--apply", action="store_true",
                    help="Persist changes; default is dry-run.")
    args = ap.parse_args()

    target = Path(args.target)
    source = Path(args.source)

    for path in (target, source):
        if not path.exists():
            print(f"ERROR: {path} does not exist", file=sys.stderr)
            return 1

    target_backup = target.with_suffix(target.suffix + ".pre-merge")
    if args.apply and not target_backup.exists():
        print(
            f"ERROR: backup {target_backup.name} not found. Phase 10 "
            "requires a pre-merge snapshot before any --apply run.",
            file=sys.stderr,
        )
        return 1

    mode = "APPLYING" if args.apply else "DRY RUN"
    print(f"=== Phase 10 merge — {mode} ===")
    print(f"  target: {target}")
    print(f"  source: {source}\n")

    conn = sqlite3.connect(target)
    conn.execute(f"ATTACH DATABASE ? AS src", (str(source),))
    cur = conn.cursor()

    pre_check(cur)
    a_humdrum = update_humdrum_gt(cur, args.apply)
    b_q6 = update_q6_text(cur, args.apply)
    c_rescore = rescore_humdrum_responses(cur, args.apply)
    d_inserted = copy_v2_responses(cur, args.apply)

    print()
    print("=== Summary ===")
    print(f"  humdrum GT rows updated: {a_humdrum}")
    print(f"  Q6 question_text rows updated: {b_q6}")
    print(f"  v1 humdrum responses rescored: {c_rescore['changed']} "
          f"(of {c_rescore['scanned']} scanned)")
    print(f"  v2 responses inserted: {d_inserted['inserted']} "
          f"(skipped existing: {d_inserted['skipped']})")

    if args.apply:
        conn.commit()
        print("\nCommitted.")
    else:
        print("\n(dry run — no changes written. Re-run with --apply.)")

    conn.close()
    return 0


def pre_check(cur: sqlite3.Cursor) -> None:
    """Refuse to merge if the two DBs disagree on something we expected
    to be identical (passages, question_types, answer columns other than
    humdrum). Schema drift or unexpected divergence should stop the run."""

    def equal(table: str, key: str) -> bool:
        a = cur.execute(f"SELECT * FROM main.{table} ORDER BY {key}").fetchall()
        b = cur.execute(f"SELECT * FROM src.{table} ORDER BY {key}").fetchall()
        return a == b

    if not equal("passages", "passage_id"):
        raise SystemExit("ABORT: passages tables differ between target and source.")
    if not equal("question_types", "question_type_id"):
        raise SystemExit("ABORT: question_types tables differ between target and source.")

    expected_text_diffs = cur.execute("""
        SELECT COUNT(*) FROM main.questions m
        JOIN src.questions s USING (question_id)
        WHERE m.question_text != s.question_text
          AND m.question_type_id != 6
    """).fetchone()[0]
    if expected_text_diffs != 0:
        raise SystemExit(
            f"ABORT: {expected_text_diffs} non-Q6 question_text diffs between target and source"
        )

    for col in ("answer_abc", "answer_mei", "answer_musicxml"):
        diffs = cur.execute(f"""
            SELECT COUNT(*) FROM main.questions m
            JOIN src.questions s USING (question_id)
            WHERE COALESCE(m.{col},'') != COALESCE(s.{col},'')
        """).fetchone()[0]
        if diffs != 0:
            raise SystemExit(f"ABORT: {diffs} {col} diffs between target and source")

    print("pre-check: passages/question_types identical, "
          "answer_abc/mei/musicxml identical, "
          "non-Q6 question_text identical. OK.\n")


def update_humdrum_gt(cur: sqlite3.Cursor, apply: bool) -> int:
    """Copy source.questions.answer_humdrum into target for any row that differs."""
    rows = cur.execute("""
        SELECT m.question_id, m.answer_humdrum, s.answer_humdrum
        FROM main.questions m
        JOIN src.questions s USING (question_id)
        WHERE COALESCE(m.answer_humdrum,'') != COALESCE(s.answer_humdrum,'')
        ORDER BY m.question_id
    """).fetchall()

    print(f"[A] humdrum GT updates ({len(rows)} rows differ):")
    for qid, old, new in rows:
        print(f"      {qid}: {old!r} -> {new!r}")
        if apply:
            cur.execute(
                "UPDATE questions SET answer_humdrum=? WHERE question_id=?",
                (new, qid),
            )
    return len(rows)


def update_q6_text(cur: sqlite3.Cursor, apply: bool) -> int:
    """Copy source.questions.question_text into target for Q6 rows."""
    rows = cur.execute("""
        SELECT m.question_id, m.question_text, s.question_text
        FROM main.questions m
        JOIN src.questions s USING (question_id)
        WHERE m.question_type_id = 6
          AND m.question_text != s.question_text
        ORDER BY m.question_id
    """).fetchall()

    print(f"\n[B] Q6 question_text updates ({len(rows)} rows differ):")
    if rows:
        first = rows[0]
        print(f"      sample {first[0]}:")
        print(f"        old: {first[1][:120]}...")
        print(f"        new: {first[2][:120]}...")
        print(f"      (and {len(rows) - 1} more identical Q6 rewordings)")
        if apply:
            cur.executemany(
                "UPDATE questions SET question_text=? WHERE question_id=?",
                [(new, qid) for qid, _, new in rows],
            )
    return len(rows)


def rescore_humdrum_responses(cur: sqlite3.Cursor, apply: bool) -> dict:
    """Recompute is_correct for every existing target humdrum response against
    the GT currently stored in target.questions. Idempotent: if step A has
    already run, the GT is already updated and this still flips the stale
    is_correct flags into agreement.

    Scoped to humdrum because Phase 10's only GT change is humdrum. Q6 prompt
    text changes do NOT trigger rescoring (per user decision in HANDOFF.md)."""
    rows = cur.execute("""
        SELECT r.id, r.question_id, r.model, r.extracted_answer, r.is_correct,
               q.answer_humdrum
        FROM main.llm_responses r
        JOIN main.questions q USING (question_id)
        WHERE r.format = 'humdrum'
        ORDER BY r.question_id, r.model
    """).fetchall()

    print(f"\n[C] Rescoring humdrum responses against current target GT "
          f"({len(rows)} rows scanned):")
    changed = 0
    for row_id, qid, model, extracted, old_correct, gt in rows:
        new_correct = bool(compare_answers(extracted or "", gt or ""))
        if new_correct == bool(old_correct):
            continue
        print(f"      {qid} {model}: extracted={extracted!r} "
              f"is_correct {bool(old_correct)} -> {new_correct} (gt={gt!r})")
        if apply:
            cur.execute(
                "UPDATE llm_responses SET is_correct=? WHERE id=?",
                (1 if new_correct else 0, row_id),
            )
        changed += 1
    if changed == 0:
        print("      (no is_correct flips — already consistent)")
    return {"scanned": len(rows), "changed": changed}


def copy_v2_responses(cur: sqlite3.Cursor, apply: bool) -> dict:
    """Insert every src.llm_responses row into target via INSERT OR IGNORE.
    Returns counts of newly inserted vs already-present rows."""
    src_total = cur.execute("SELECT COUNT(*) FROM src.llm_responses").fetchone()[0]

    pre_target = cur.execute("SELECT COUNT(*) FROM main.llm_responses").fetchone()[0]
    print(f"\n[D] Copying llm_responses: src has {src_total} rows, "
          f"target has {pre_target} rows pre-merge.")

    by_model_format = cur.execute("""
        SELECT model, format, COUNT(*) FROM src.llm_responses
        GROUP BY model, format ORDER BY model, format
    """).fetchall()
    for model, fmt, n in by_model_format:
        print(f"      to copy: {model} / {fmt}: {n}")

    if apply:
        cur.execute("""
            INSERT OR IGNORE INTO main.llm_responses
                (question_id, passage_id, format, model,
                 extracted_answer, is_correct, timestamp)
            SELECT question_id, passage_id, format, model,
                   extracted_answer, is_correct, timestamp
            FROM src.llm_responses
        """)
        post_target = cur.execute("SELECT COUNT(*) FROM main.llm_responses").fetchone()[0]
        inserted = post_target - pre_target
        skipped = src_total - inserted
    else:
        existing = cur.execute("""
            SELECT COUNT(*) FROM src.llm_responses s
            WHERE EXISTS (
                SELECT 1 FROM main.llm_responses m
                WHERE m.question_id = s.question_id
                  AND m.passage_id = s.passage_id
                  AND m.format = s.format
                  AND m.model = s.model
            )
        """).fetchone()[0]
        inserted = src_total - existing
        skipped = existing

    return {"inserted": inserted, "skipped": skipped}


if __name__ == "__main__":
    sys.exit(main())

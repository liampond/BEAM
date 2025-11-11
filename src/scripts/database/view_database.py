#!/usr/bin/env python3
"""View the benchmark database in various formats."""

import sqlite3
import sys
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional


def export_to_csv(rows, headers, output_file):
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"\n✓ Exported to: {output_file}")


def export_to_markdown(rows, headers, output_file, metadata):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Benchmark Database Export\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Total Questions:** {metadata['total_questions']}\n")
        f.write(f"**Total Passages:** {metadata['total_passages']}\n")
        f.write(f"**Total Test Cases:** {metadata['total_test_cases']}\n\n")
        
        alignments = [':---:' if h in ['question-id', 'passage-id', 'bars', 'difficulty', 'test-cases'] else ':---' for h in headers]
        
        f.write('| ' + ' | '.join(headers) + ' |\n')
        f.write('| ' + ' | '.join(alignments) + ' |\n')
        
        for row in rows:
            escaped_row = [str(cell).replace('|', '\\|') for cell in row]
            f.write('| ' + ' | '.join(escaped_row) + ' |\n')
    
    print(f"\n✓ Exported to: {output_file}")


def format_terminal_output(rows, headers):
    if not rows:
        return "No questions found."
    
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    
    max_widths = {
        'question-id': 12, 'passage-id': 11, 'passage': 30, 'bars': 5,
        'question': 50, 'difficulty': 10, 'test-cases': 11,
        'response-musicxml': 18, 'response-abc': 15, 'response-mei': 15, 'response-humdrum': 18
    }
    
    for i, header in enumerate(headers):
        if header in max_widths:
            widths[i] = min(widths[i], max_widths[header])
    
    lines = []
    header_line = '  '.join(h.ljust(w) for h, w in zip(headers, widths))
    separator = '  '.join('─' * w for w in widths)
    
    lines.append(header_line)
    lines.append(separator)
    
    for row in rows:
        cells = []
        for cell, width in zip(row, widths):
            cell_str = str(cell)
            if len(cell_str) > width:
                cell_str = cell_str[:width-1] + '…'
            cells.append(cell_str.ljust(width))
        lines.append('  '.join(cells))
    
    return '\n'.join(lines)


def view_database(db_path, limit=None, passage_id=None, question_id=None, 
                  show_answers=True, export_format=None, output_file=None):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    where_clauses, params = [], []
    
    if passage_id:
        where_clauses.append("p.passage_id = ?")
        params.append(passage_id)
    
    if question_id:
        where_clauses.append("q.question_id = ?")
        params.append(question_id)
    
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    limit_sql = f"LIMIT {limit}" if limit else ""
    
    cursor.execute(f"""
        SELECT 
            q.question_id, p.passage_id, p.description, p.num_measures, q.question_text,
            q.difficulty, q.answer_musicxml, q.answer_abc, q.answer_mei, q.answer_humdrum,
            COUNT(tc.test_case_id) as num_test_cases
        FROM questions q
        JOIN passages p ON q.passage_id = p.passage_id
        LEFT JOIN test_cases tc ON q.question_id = tc.question_id
        {where_sql}
        GROUP BY q.question_id
        ORDER BY q.question_id
        {limit_sql}
    """, params)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("No questions found matching the criteria.")
        conn.close()
        return
    
    cursor.execute("SELECT COUNT(*) FROM questions")
    total_questions = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM passages")
    total_passages = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM test_cases")
    total_test_cases = cursor.fetchone()[0]
    
    metadata = {
        'total_questions': total_questions,
        'total_passages': total_passages,
        'total_test_cases': total_test_cases
    }
    
    if show_answers:
        headers = ['question-id', 'passage-id', 'passage', 'bars', 'question', 'difficulty', 
                   'response-musicxml', 'response-abc', 'response-mei', 'response-humdrum', 'test-cases']
        formatted_rows = [
            [f"Q{r[0]:03d}", f"P{r[1]:03d}", r[2], r[3], r[4], r[5] or '', 
             r[6] or '', r[7] or '', r[8] or '', r[9] or '', r[10]]
            for r in rows
        ]
    else:
        headers = ['question-id', 'passage-id', 'passage', 'bars', 'question', 'difficulty', 'test-cases']
        formatted_rows = [
            [f"Q{r[0]:03d}", f"P{r[1]:03d}", r[2], r[3], r[4], r[5] or '', r[10]]
            for r in rows
        ]
    
    if export_format == 'csv':
        if not output_file:
            output_file = f"benchmark_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        export_to_csv(formatted_rows, headers, output_file)
    elif export_format in ['md', 'markdown']:
        if not output_file:
            output_file = f"benchmark_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        export_to_markdown(formatted_rows, headers, output_file, metadata)
    else:
        print("\n" + "=" * 100)
        print(f"BENCHMARK DATABASE - {len(formatted_rows)} questions")
        print("=" * 100 + "\n")
        print(format_terminal_output(formatted_rows, headers))
        print("\n" + "─" * 100)
        print(f"Showing {len(rows)} of {total_questions} questions from {total_passages} passages")
        print(f"Total test cases: {total_test_cases}")
        print("─" * 100 + "\n")
    
    conn.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='View the benchmark database')
    parser.add_argument('--db', default='benchmark.db')
    parser.add_argument('--limit', '-l', type=int)
    parser.add_argument('--passage', '-p', type=int)
    parser.add_argument('--question', '-q', type=int)
    parser.add_argument('--no-answers', action='store_true')
    parser.add_argument('--export', '-e', choices=['csv', 'md', 'markdown'])
    parser.add_argument('--output', '-o')
    
    args = parser.parse_args()
    
    db_path = Path(args.db)
    if not db_path.exists():
        db_path = Path.cwd() / args.db
        if not db_path.exists():
            print(f"Error: Database not found: {args.db}")
            sys.exit(1)
    
    view_database(
        str(db_path), limit=args.limit, passage_id=args.passage, 
        question_id=args.question, show_answers=not args.no_answers,
        export_format=args.export, output_file=args.output
    )


if __name__ == '__main__':
    main()

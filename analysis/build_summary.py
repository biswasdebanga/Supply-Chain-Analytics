"""
build_summary.py
-----------------
Runs the SQL analysis queries against sql/supply_chain.db and produces:
  - analysis/summary.json   (feeds the interactive dashboard)
  - analysis/*.csv          (one CSV per analysis, feeds the Excel workbook)

Usage:
    python analysis/build_summary.py
"""
import json
import os
import re
import sqlite3

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "sql", "supply_chain.db")
SQL_PATH = os.path.join(BASE_DIR, "sql", "analysis_queries.sql")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def split_queries(sql_text):
    """Split the annotated SQL file into (name, query) pairs using the
    numbered section headers ('-- N. TITLE') as boundaries. Comment lines
    are left in the returned statement text; sqlite ignores them."""
    header_re = re.compile(r"^-- (\d+)\. (.+)$", re.MULTILINE)
    matches = list(header_re.finditer(sql_text))
    queries = []
    for idx, m in enumerate(matches):
        num, title = m.group(1), m.group(2).strip()
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(sql_text)
        body = sql_text[start:end]
        # drop the closing '-- ====' banner line right after the title, if present
        body = re.sub(r"^\n-- =+\n", "\n", body, count=1)
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        queries.append((f"{num}_{slug}", title, body.strip()))
    return queries


def main():
    with open(SQL_PATH) as f:
        sql_text = f.read()

    queries = split_queries(sql_text)
    conn = sqlite3.connect(DB_PATH)

    summary = {}
    for slug, title, statement in queries:
        df = pd.read_sql_query(statement, conn)
        csv_path = os.path.join(OUT_DIR, f"{slug}.csv")
        df.to_csv(csv_path, index=False)
        summary[slug] = {
            "title": title,
            "columns": list(df.columns),
            "rows": df.to_dict(orient="records"),
        }
        print(f"  [{slug}] {title}: {len(df)} rows -> {os.path.basename(csv_path)}")

    conn.close()

    out_json = os.path.join(OUT_DIR, "summary.json")
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nWrote {out_json}")


if __name__ == "__main__":
    main()

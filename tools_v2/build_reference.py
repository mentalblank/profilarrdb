"""Build the canonical Profilarr v2 reference database.

Creates a SQLite DB from the PCD schema, then replays every op in
``database-2/ops/*.sql`` in numeric-prefix order. The result (reference.db)
is the ground-truth official state that our generated ops must reproduce.

Usage:
    python tools_v2/build_reference.py
"""

import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "profilarr-develop" / "docs" / "backend" / "0.schema.sql"
OPS_DIR = ROOT / "database-2" / "ops"
OUT_DB = ROOT / "tools_v2" / "reference.db"

NUM_PREFIX = re.compile(r"^(\d+)\.")


def op_sort_key(path: Path):
    m = NUM_PREFIX.match(path.name)
    return (int(m.group(1)) if m else 1 << 30, path.name)


def split_statements(sql: str):
    """Split SQL into statements on top-level ';'.

    Respects single-quoted string literals (with '' escapes) and strips
    ``--`` line comments. Good enough for the export-style ops in this repo
    (no block comments, no dollar-quoting).
    """
    stmts = []
    buf = []
    i = 0
    n = len(sql)
    in_str = False
    while i < n:
        ch = sql[i]
        if in_str:
            buf.append(ch)
            if ch == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        if ch == "'":
            in_str = True
            buf.append(ch)
            i += 1
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            # line comment: skip to end of line
            j = sql.find("\n", i)
            if j == -1:
                break
            i = j + 1
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def main() -> int:
    if not SCHEMA.exists():
        print(f"Schema not found: {SCHEMA}")
        return 1
    if not OPS_DIR.exists():
        print(f"Ops dir not found: {OPS_DIR}")
        return 1

    try:
        OUT_DB.unlink(missing_ok=True)
    except PermissionError:
        print(f"{OUT_DB} is locked by another process; close it and retry.")
        return 1

    conn = sqlite3.connect(OUT_DB)
    # FK enforcement OFF during bulk replay: ops are export-ordered and
    # internally consistent, but cross-op insert order can trip composite FKs.
    conn.execute("PRAGMA foreign_keys = OFF;")
    # Bulk-load speed: skip fsync/journal (throwaway reference DB).
    conn.execute("PRAGMA synchronous = OFF;")
    conn.execute("PRAGMA journal_mode = OFF;")

    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    print(f"Schema loaded from {SCHEMA.name}")

    ops = sorted(OPS_DIR.glob("*.sql"), key=op_sort_key)
    print(f"Replaying {len(ops)} ops...")

    skipped = 0
    for op in ops:
        sql = op.read_text(encoding="utf-8")
        for stmt in split_statements(sql):
            try:
                conn.execute(stmt)
            except sqlite3.Error as e:
                skipped += 1
                first_line = stmt.splitlines()[0][:90]
                print(f"  SKIP {op.name}: {e} | {first_line}")
    conn.commit()

    print("\n=== Reference DB summary ===")
    tables = [
        "tags", "languages", "regular_expressions", "qualities",
        "custom_formats", "custom_format_conditions", "condition_patterns",
        "condition_sources", "condition_languages", "quality_profiles",
        "quality_profile_custom_formats", "quality_groups",
        "quality_group_members", "radarr_naming", "sonarr_naming",
        "radarr_quality_definitions", "delay_profiles",
    ]
    for t in tables:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t:35s} {n}")
        except sqlite3.Error as e:
            print(f"  {t:35s} ERR {e}")

    conn.close()
    print(f"\nWrote {OUT_DB} (skipped statements: {skipped})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

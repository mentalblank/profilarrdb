"""Validate generated v2 ops against the PCD schema (FK enforced).

Loads the schema, seeds dependency-provided core rows (languages, qualities)
that live in the schema dependency rather than database-2, applies the
generated ops/*.sql, and reports FK/constraint failures + counts.

Usage:
    python tools_v2/validate_build.py
"""

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_reference import split_statements
from utils.ops_writer import CANONICAL_LANGUAGES
from utils.mappings.qualities import QUALITY_MAPPING

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "profilarr-develop" / "docs" / "backend" / "0.schema.sql"
OPS = sorted((ROOT / "ops").glob("*.sql"),
             key=lambda p: int(re.match(r"(\d+)", p.name).group(1))
             if re.match(r"(\d+)", p.name) else 1 << 30)


def main() -> int:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    # Seed dependency-provided core rows (languages, qualities) the same way
    # Profilarr's schema dependency does. Prefer AUTHORITATIVE names from
    # reference.db (the official DB, proven to load in Profilarr) so this catches
    # quality/language names that don't actually exist in Profilarr's tables;
    # fall back to our mappings if reference.db is absent.
    ref = ROOT / "tools_v2" / "reference.db"
    seeded_from_ref = False
    if ref.exists():
        rc = sqlite3.connect(ref)
        qn = set()
        for t, c in [("quality_profile_qualities", "quality_name"),
                     ("quality_group_members", "quality_name"),
                     ("radarr_quality_definitions", "quality_name"),
                     ("sonarr_quality_definitions", "quality_name")]:
            qn |= {r[0] for r in rc.execute(
                f"SELECT DISTINCT {c} FROM {t} WHERE {c} IS NOT NULL")}
        rc.close()
        if qn:
            for q in sorted(qn):
                conn.execute("INSERT OR IGNORE INTO qualities (name) VALUES (?)", (q,))
            seeded_from_ref = True
    if not seeded_from_ref:
        for q in sorted({info["name"] for info in QUALITY_MAPPING.values()}):
            conn.execute("INSERT OR IGNORE INTO qualities (name) VALUES (?)", (q,))
    # Languages: CANONICAL_LANGUAGES = all valid arr languages (Profilarr's table
    # is the full arr language set, so this is the right authority).
    for lang in CANONICAL_LANGUAGES:
        conn.execute("INSERT OR IGNORE INTO languages (name) VALUES (?)", (lang,))
    print(f"(qualities seeded from {'reference.db' if seeded_from_ref else 'QUALITY_MAPPING'})")

    fails = 0
    samples = []
    for op in OPS:
        for stmt in split_statements(op.read_text(encoding="utf-8")):
            try:
                conn.execute(stmt)
            except sqlite3.Error as e:
                fails += 1
                if len(samples) < 15:
                    samples.append(f"{op.name}: {e} | {stmt.splitlines()[0][:80]}")
    conn.commit()

    for s in samples:
        print("FAIL", s)
    print("--- total fails:", fails)

    for t in ["tags", "regular_expressions", "custom_formats",
              "custom_format_conditions", "condition_patterns",
              "condition_sources", "condition_resolutions",
              "condition_quality_modifiers", "condition_indexer_flags",
              "condition_languages", "condition_release_types",
              "quality_profiles", "quality_profile_qualities",
              "quality_groups", "quality_group_members",
              "quality_profile_custom_formats", "radarr_naming",
              "sonarr_naming", "radarr_media_settings", "sonarr_media_settings",
              "radarr_quality_definitions", "sonarr_quality_definitions"]:
        print(f"  {t:32s}", conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    conn.close()
    return 0 if fails == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

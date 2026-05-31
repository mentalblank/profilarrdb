"""Cross-check the generated v2 DB against Radarr/Sonarr source compatibility.

Two checks per emitted custom-format condition:
  1. Condition TYPE is supported by the target arr(s) — derived directly from
     arrSource/*/CustomFormats/Specifications/*.cs filenames.
  2. Condition VALUE (source/resolution/quality_modifier/release_type/
     indexer_flag/language) is valid for the target arr(s), using the scripts
     mappings (which mirror the arr enums) + canonical languages.

A condition with arr_type='all' must satisfy BOTH arrs.

Usage:
    python tools_v2/check_arr_compat.py
"""

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_reference import split_statements
from utils.ops_writer import CANONICAL_LANGUAGES, canonical_language
from utils.mappings.qualities import QUALITY_MAPPING
from utils.mappings.source import SOURCE_MAPPING
from utils.mappings.indexer_flags import INDEXER_FLAG_MAPPING
from utils.mappings.quality_modifiers import QUALITY_MODIFIER_MAPPING
from utils.mappings.release_type import RELEASE_TYPE_MAPPING
from utils.mappings.misc import RESOLUTION_MAPPING

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "profilarr-develop" / "docs" / "backend" / "0.schema.sql"
OP = ROOT / "ops" / "0.base.sql"

SPEC_DIRS = {
    "radarr": ROOT / "arrSource/Radarr-develop/src/NzbDrone.Core/CustomFormats/Specifications",
    "sonarr": ROOT / "arrSource/Sonarr-5-develop/src/NzbDrone.Core/CustomFormats/Specifications",
}

# CF spec class name -> PCD condition type.
SPEC_TYPE = {
    "ReleaseTitle": "release_title",
    "ReleaseGroup": "release_group",
    "Edition": "edition",
    "Language": "language",
    "IndexerFlag": "indexer_flag",
    "QualityModifier": "quality_modifier",
    "Resolution": "resolution",
    "Source": "source",
    "Size": "size",
    "Year": "year",
    "ReleaseType": "release_type",
}


def valid_types_for(arr):
    types = set()
    for f in SPEC_DIRS[arr].glob("*Specification.cs"):
        base = f.stem.replace("Specification", "")
        if base in ("CustomFormat", "ICustomFormat", "Regex", "RegexBase"):
            continue
        if base in SPEC_TYPE:
            types.add(SPEC_TYPE[base])
    return types


def arrs_for(arr_type):
    return ["radarr", "sonarr"] if arr_type == "all" else [arr_type]


def main() -> int:
    valid_types = {a: valid_types_for(a) for a in ("radarr", "sonarr")}
    print("Valid condition types (from arrSource):")
    for a in ("radarr", "sonarr"):
        print(f"  {a}: {sorted(valid_types[a])}")

    valid_vals = {
        "source": {a: set(SOURCE_MAPPING[a].values()) for a in ("radarr", "sonarr")},
        "indexer_flag": {a: set(INDEXER_FLAG_MAPPING[a].values()) for a in ("radarr", "sonarr")},
        "quality_modifier": {a: set(QUALITY_MODIFIER_MAPPING[a].values()) for a in ("radarr", "sonarr")},
        "release_type": {a: set(RELEASE_TYPE_MAPPING[a].values()) for a in ("radarr", "sonarr")},
        "resolution": {a: set(RESOLUTION_MAPPING.values()) for a in ("radarr", "sonarr")},
        "language": {a: {x.lower() for x in CANONICAL_LANGUAGES} for a in ("radarr", "sonarr")},
    }

    # Load DB.
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    for s in split_statements(OP.read_text(encoding="utf-8")):
        try:
            conn.execute(s)
        except sqlite3.Error:
            pass
    conn.row_factory = sqlite3.Row

    side = {
        "source": ("condition_sources", "source"),
        "resolution": ("condition_resolutions", "resolution"),
        "quality_modifier": ("condition_quality_modifiers", "quality_modifier"),
        "indexer_flag": ("condition_indexer_flags", "flag"),
        "release_type": ("condition_release_types", "release_type"),
        "language": ("condition_languages", "language_name"),
    }

    type_violations = []
    value_violations = []

    conds = conn.execute(
        "SELECT custom_format_name, name, type, arr_type FROM custom_format_conditions"
    ).fetchall()
    for c in conds:
        ctype, arr_type = c["type"], c["arr_type"]
        for arr in arrs_for(arr_type):
            if ctype not in valid_types[arr]:
                type_violations.append(
                    f"{c['custom_format_name']} / {c['name']}: type '{ctype}' "
                    f"not valid for {arr} (arr_type={arr_type})")

        if ctype in side:
            table, col = side[ctype]
            row = conn.execute(
                f"SELECT {col} AS v FROM {table} WHERE custom_format_name=? AND condition_name=?",
                (c["custom_format_name"], c["name"])).fetchone()
            if row is None:
                continue
            val = row["v"]
            cmp = val.lower() if ctype == "language" else val
            for arr in arrs_for(arr_type):
                allowed = valid_vals.get(ctype, {}).get(arr)
                if allowed is not None and cmp not in allowed:
                    value_violations.append(
                        f"{c['custom_format_name']} / {c['name']}: {ctype} value "
                        f"'{val}' not valid for {arr} (arr_type={arr_type})")

    print(f"\nConditions checked: {len(conds)}")
    print(f"TYPE violations:  {len(type_violations)}")
    for v in type_violations[:20]:
        print("  ", v)
    print(f"VALUE violations: {len(value_violations)}")
    for v in value_violations[:20]:
        print("  ", v)

    conn.close()
    return 0 if not type_violations and not value_violations else 2


if __name__ == "__main__":
    sys.exit(main())

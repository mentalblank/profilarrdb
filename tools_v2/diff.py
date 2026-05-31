"""Diff generated YAML items against the canonical reference DB.

Reads the v1 YAML trees this repo currently produces (custom_formats/,
regex_patterns/, profiles/) and compares them to tools_v2/reference.db
(built by build_reference.py). Writes a markdown report to
tools_v2/diff_report.md.

Purpose: quantify the gap and surface the actionable bits for the v2 retarget
(which shared regex patterns differ, the official tag taxonomy, etc.).

Usage:
    python tools_v2/diff.py
"""

import glob
import os
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "tools_v2" / "reference.db"
REPORT = ROOT / "tools_v2" / "diff_report.md"


def stems(dir_name):
    out = {}
    for f in glob.glob(str(ROOT / dir_name / "*.yml")):
        stem = os.path.splitext(os.path.basename(f))[0]
        try:
            with open(f, "r", encoding="utf-8") as fh:
                out[stem] = yaml.safe_load(fh)
        except Exception as e:  # noqa: BLE001
            out[stem] = {"_parse_error": str(e)}
    return out


def section(lines, title):
    lines.append("")
    lines.append(f"## {title}")
    lines.append("")


def name_block(lines, label, mine, official):
    only_mine = sorted(mine - official)
    only_off = sorted(official - mine)
    both = mine & official
    lines.append(f"- **{label}**: mine={len(mine)} official={len(official)} "
                 f"shared={len(both)} only-mine={len(only_mine)} "
                 f"only-official={len(only_off)}")
    return both, only_mine, only_off


def main() -> int:
    if not DB.exists():
        print(f"Missing {DB}; run build_reference.py first.")
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    off_rx = {r["name"]: r["pattern"] for r in
              conn.execute("SELECT name, pattern FROM regular_expressions")}
    off_cf = {r["name"]: dict(r) for r in
              conn.execute("SELECT name, description, include_in_rename FROM custom_formats")}
    off_qp = set(r[0] for r in conn.execute("SELECT name FROM quality_profiles"))

    my_rx = stems("regex_patterns")
    my_cf = stems("custom_formats")
    my_qp = stems("profiles")

    lines = ["# Generated YAML vs official reference.db", ""]

    # ---- Regex ----
    section(lines, "Regular expressions")
    both, only_mine, only_off = name_block(
        lines, "names", set(my_rx), set(off_rx))
    pat_diff = []
    for name in sorted(both):
        mine_pat = (my_rx[name] or {}).get("pattern")
        if mine_pat != off_rx[name]:
            pat_diff.append((name, mine_pat, off_rx[name]))
    lines.append(f"- **shared with DIFFERING pattern**: {len(pat_diff)} "
                 f"(of {len(both)} shared)")
    if pat_diff:
        lines.append("")
        lines.append("| regex | mine | official |")
        lines.append("|---|---|---|")
        for name, m, o in pat_diff[:40]:
            mm = (m or "").replace("|", "\\|")
            oo = (o or "").replace("|", "\\|")
            lines.append(f"| {name} | `{mm}` | `{oo}` |")
        if len(pat_diff) > 40:
            lines.append(f"| … | … | (+{len(pat_diff) - 40} more) |")
    lines.append("")
    lines.append(f"<details><summary>only in MINE ({len(only_mine)})</summary>\n\n"
                 + ", ".join(only_mine) + "\n\n</details>")
    lines.append(f"<details><summary>only in OFFICIAL ({len(only_off)})</summary>\n\n"
                 + ", ".join(only_off) + "\n\n</details>")

    # ---- Custom formats ----
    section(lines, "Custom formats")
    both, only_mine, only_off = name_block(
        lines, "names", set(my_cf), set(off_cf))
    lines.append("")
    lines.append(f"<details><summary>shared ({len(both)})</summary>\n\n"
                 + ", ".join(sorted(both)) + "\n\n</details>")
    lines.append(f"<details><summary>only in MINE ({len(only_mine)})</summary>\n\n"
                 + ", ".join(only_mine) + "\n\n</details>")
    lines.append(f"<details><summary>only in OFFICIAL ({len(only_off)})</summary>\n\n"
                 + ", ".join(only_off) + "\n\n</details>")

    # ---- Profiles ----
    section(lines, "Quality profiles")
    both, only_mine, only_off = name_block(
        lines, "names", set(my_qp), off_qp)
    lines.append("")
    lines.append(f"- only-mine: {', '.join(only_mine)}")
    lines.append(f"- only-official: {', '.join(sorted(only_off))}")

    # ---- Official tag taxonomy (drives tags.py rework) ----
    section(lines, "Official tag taxonomy (target for tags.py)")
    tag_rows = conn.execute(
        "SELECT t.name, COUNT(cft.custom_format_name) AS n "
        "FROM tags t LEFT JOIN custom_format_tags cft ON cft.tag_name = t.name "
        "GROUP BY t.name ORDER BY n DESC, t.name").fetchall()
    lines.append("| tag | #CFs |")
    lines.append("|---|---|")
    for r in tag_rows:
        lines.append(f"| {r['name']} | {r['n']} |")

    # ---- Condition type usage (official) ----
    section(lines, "Official condition types in use")
    for r in conn.execute(
            "SELECT type, COUNT(*) n FROM custom_format_conditions "
            "GROUP BY type ORDER BY n DESC"):
        lines.append(f"- {r['type']}: {r['n']}")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    conn.close()
    print(f"Wrote {REPORT}")
    # Echo headline numbers
    for ln in lines:
        if ln.startswith("- **names**") or "DIFFERING pattern" in ln:
            print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())

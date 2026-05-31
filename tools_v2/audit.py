"""One-shot audit: TRaSH coverage, custom additions, and ordering.

Read-only. Complements check_mappings.py / validate_build.py / check_arr_compat.py.

Usage: python tools_v2/audit.py
"""

import glob
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_reference import split_statements
from generate import build_cfs_and_regex, build_profiles, find_guides_dir
from utils.profiles import should_skip
from utils.mappings.misc import CUSTOM_FORMATS, CUSTOM_PATTERNS, EXTRA_LQ_GROUPS

ROOT = Path(__file__).resolve().parent.parent


def stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def main():
    gd = find_guides_dir()

    # ---- TRaSH coverage ----
    print("=== TRaSH coverage ===")
    for arr in ("radarr", "sonarr"):
        files = glob.glob(str(gd / arr / "cf" / "*.json"))
        skipped = []
        for f in files:
            d = json.load(open(f, encoding="utf-8"))
            if should_skip(d, stem(f)):
                skipped.append(stem(f))
        print(f"  {arr}: {len(files)} cf json, {len(skipped)} skipped (french/german/sqp)")

    m = build_cfs_and_regex(gd)
    print(f"  loaded radarr={len(m['radarr_raw'])} sonarr={len(m['sonarr_raw'])} "
          f"-> merged CFs={len(m['merged_cfs'])}, regex={len(m['final_patterns_dict'])}")

    # ---- custom additions ----
    print("=== custom additions ===")
    names = {cf["name"] for cf in m["merged_cfs"].values()}
    cust_present = [cf["name"] for cf in CUSTOM_FORMATS.values() if cf["name"] in names]
    print(f"  CUSTOM_FORMATS in build: {len(cust_present)}/{len(CUSTOM_FORMATS)}")
    missing_cust = [cf["name"] for cf in CUSTOM_FORMATS.values() if cf["name"] not in names]
    if missing_cust:
        print(f"    MISSING: {missing_cust}")
    pat_present = sum(1 for k in CUSTOM_PATTERNS if k.split(" (")[0] in m["final_patterns_dict"])
    print(f"  CUSTOM_PATTERNS in regex: {pat_present}/{len(CUSTOM_PATTERNS)}")
    for lq in ("LQ", "LQ (Release Title)"):
        cf = next((c for c in m["merged_cfs"].values() if c["name"] == lq), None)
        if cf:
            groups = {c["name"] for c in cf["conditions"]}
            present = [g for g in EXTRA_LQ_GROUPS if g in groups]
            print(f"  {lq}: {len(present)}/{len(EXTRA_LQ_GROUPS)} EXTRA_LQ_GROUPS injected")
        else:
            print(f"  {lq}: NOT FOUND")

    # ---- custom profiles ----
    print("=== custom profiles ===")
    profiles, _ = build_profiles(gd, m)
    pnames = [p["name"] for p in profiles]
    customs = [n for n in pnames if any(k in n for k in
               ("Movies", "TV (", "Anime"))]
    print(f"  total profiles={len(pnames)}; custom copies={len(customs)}")
    for n in customs:
        print(f"    {n}")

    # ---- unexpected condition types ----
    KNOWN = {"release_title", "release_group", "edition", "language", "indexer_flag",
             "quality_modifier", "resolution", "source", "release_type", "size", "year"}
    bad = {}
    for cf in m["merged_cfs"].values():
        for c in cf["conditions"]:
            t = c.get("type")
            if t not in KNOWN:
                bad.setdefault(t, 0)
                bad[t] += 1
    print("=== condition types ===")
    print(f"  unexpected types: {bad if bad else 'none'}")

    # ---- ordering checks (built DB) ----
    print("=== ordering (built DB) ===")
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.executescript((ROOT / "profilarr-develop/docs/backend/0.schema.sql").read_text(encoding="utf-8"))
    for s in split_statements((ROOT / "ops/0.base.sql").read_text(encoding="utf-8")):
        try:
            conn.execute(s)
        except sqlite3.Error:
            pass

    # quality_profile_qualities positions: contiguous 0..n-1 per profile?
    bad_pos = []
    for (prof,) in conn.execute("SELECT DISTINCT quality_profile_name FROM quality_profile_qualities"):
        rows = [r[0] for r in conn.execute(
            "SELECT position FROM quality_profile_qualities WHERE quality_profile_name=? ORDER BY position",
            (prof,))]
        if rows != list(range(len(rows))):
            bad_pos.append((prof, rows))
    print(f"  profile quality positions contiguous-from-0: "
          f"{'OK' if not bad_pos else 'BAD ' + str(bad_pos[:3])}")

    # group member positions contiguous per group?
    bad_gpos = []
    for prof, grp in conn.execute(
            "SELECT DISTINCT quality_profile_name, quality_group_name FROM quality_group_members"):
        rows = [r[0] for r in conn.execute(
            "SELECT position FROM quality_group_members WHERE quality_profile_name=? AND quality_group_name=? ORDER BY position",
            (prof, grp))]
        if rows != list(range(len(rows))):
            bad_gpos.append((prof, grp, rows))
    print(f"  group member positions contiguous-from-0: "
          f"{'OK' if not bad_gpos else 'BAD ' + str(bad_gpos[:3])}")

    # exactly one upgrade_until per profile?
    bad_cut = []
    for (prof,) in conn.execute("SELECT DISTINCT quality_profile_name FROM quality_profile_qualities"):
        n = conn.execute(
            "SELECT COUNT(*) FROM quality_profile_qualities WHERE quality_profile_name=? AND upgrade_until=1",
            (prof,)).fetchone()[0]
        if n != 1:
            bad_cut.append((prof, n))
    print(f"  exactly one upgrade_until per profile: "
          f"{'OK' if not bad_cut else 'CHECK ' + str(bad_cut)}")

    conn.close()


if __name__ == "__main__":
    main()

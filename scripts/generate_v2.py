"""Generate a Profilarr v2 (PCD 2.0) database from TRaSH Guides.

Reuses the model builder in generate.py, then emits v2 `ops/*.sql` instead of
v1 YAML trees. Slice 1: regular expressions + custom formats (+ conditions).
Quality profiles and media management are TODO (later slices).

Output: ops/0.base.sql at the repo root (PCD database layout; pcd.json already there).

Usage:
    python scripts/generate_v2.py
"""

import sys
from pathlib import Path

# Allow running both as `python scripts/generate_v2.py` and from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate import build_cfs_and_regex, build_profiles, find_guides_dir
from utils.strings import clean_name
from utils.ops_writer import OpsWriter
from utils.media_management import build_naming, build_quality_definitions
from utils.tag_rules import infer_tags

# Repo root = the PCD database layout: pcd.json + ops/ live here.
OUT_DIR = Path(".")


def main() -> int:
    guides_dir = find_guides_dir()
    if not guides_dir:
        print("Error: Guides-master/docs/json not found!")
        return 1

    print("Building model from TRaSH Guides...")
    model = build_cfs_and_regex(guides_dir)
    merged_cfs = model["merged_cfs"]
    final_patterns_dict = model["final_patterns_dict"]

    w = OpsWriter()

    # Regular expressions (named entities).
    print(f"Emitting {len(final_patterns_dict)} regular expressions...")
    for name in sorted(final_patterns_dict, key=str.lower):
        w.regular_expression(
            name=clean_name(name),
            pattern=final_patterns_dict[name],
            description=None,
            regex101_id=None,
            tags=(),
        )

    # Custom formats (+ tags, conditions, condition side-tables).
    print(f"Emitting {len(merged_cfs)} custom formats...")
    cf_names = set()
    for stem, cf in merged_cfs.items():
        conditions = cf.get("conditions", [])
        tags = infer_tags(cf["name"], conditions)
        cf_names.add(cf["name"])
        w.custom_format(
            name=cf["name"],
            description=cf.get("description", ""),
            include_in_rename=cf.get("includeCustomFormatWhenRenaming", False),
            tags=tags,
            conditions=conditions,
        )

    # Quality profiles (base + custom copies).
    profiles, _ = build_profiles(guides_dir, model)
    print(f"Emitting {len(profiles)} quality profiles...")
    skipped_scores = 0
    for p in profiles:
        skipped_scores += w.quality_profile(p, known_cf_names=cf_names)
    if skipped_scores:
        print(f"  (skipped {skipped_scores} CF scores referencing unknown CFs)")

    # Media management: naming, media settings, quality definitions.
    print("Emitting media management...")
    naming = build_naming(guides_dir)
    w.radarr_naming(naming["radarr"])
    w.sonarr_naming(naming["sonarr"])
    w.media_settings("radarr", "Radarr", enable_media_info=False)
    w.media_settings("sonarr", "Sonarr", enable_media_info=False)
    qd = build_quality_definitions(guides_dir)
    w.quality_definitions("radarr", "Radarr", qd["radarr"])
    w.quality_definitions("sonarr", "Sonarr", qd["sonarr"])

    ops_dir = OUT_DIR / "ops"
    ops_dir.mkdir(parents=True, exist_ok=True)
    out = ops_dir / "0.base.sql"
    w.write(out, "Base import from TRaSH Guides")
    print(f"Wrote {out}")
    # pcd.json (the PCD manifest) already lives at the repo root.
    return 0


if __name__ == "__main__":
    sys.exit(main())

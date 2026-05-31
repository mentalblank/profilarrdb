"""TRaSH Guides model builder.

Loads TRaSH Guides JSON into the in-memory custom-format / regex / profile model
shared by the v2 ops emitter (see generate_v2.py). This module no longer writes
any output itself; run `python scripts/generate_v2.py` to build the database.
"""

import json
import copy
from pathlib import Path

from utils.strings import clean_name
from utils.regex_patterns import extract_regex, resolve_regex_names
from utils.custom_formats import (
    convert_cf_to_dict,
    sort_and_group_conditions,
    deduplicate_conditions,
    is_cf_equal,
    fuzzy_merge_cf,
    has_incompatible_language,
    arr_merge_cf,
)
from utils.profiles import process_profiles, apply_customizations, should_skip
from utils.mappings.source import SOURCE_MAPPING
from utils.mappings.misc import CUSTOM_FORMATS, CUSTOM_PATTERNS, EXTRA_LQ_GROUPS, LQ_REMOVE_GROUPS

def find_guides_dir():
    """Locate Guides-master/docs/json in the current or parent directory."""
    for prefix in [Path("."), Path("..")]:
        if (prefix / "Guides-master/docs/json").exists():
            return prefix / "Guides-master/docs/json"
    return None


def build_cfs_and_regex(guides_dir):
    """Build the custom-format and regex model from TRaSH Guides JSON.

    Returns a dict with the in-memory model shared by the v1 YAML writer and
    the v2 ops emitter:
        merged_cfs           stem -> CF dict (name, description, tags, conditions, ...)
        final_patterns_dict  regex final_name -> pattern
        resolved_patterns    (orig_name, pattern_lower) -> final_name
        final_cf_names       (service, stem) -> final CF name
        radarr_raw/sonarr_raw stem -> raw TRaSH JSON (needed for profiles)
    """
    # 1. First Pass: Load JSON and Collect all raw patterns
    raw_patterns_list = []
    radarr_raw, sonarr_raw = {}, {}
    
    print("Loading Radarr JSON and collecting patterns...")
    for f in (guides_dir / "radarr" / "cf").glob("*.json"):
        with open(f, 'r', encoding='utf-8') as jf: data = json.load(jf)
        if should_skip(data, f.stem): continue
        radarr_raw[f.stem] = data
        extract_regex(data.get("specifications", []), raw_patterns_list, "radarr")
        
    print("Loading Sonarr JSON and collecting patterns...")
    for f in (guides_dir / "sonarr" / "cf").glob("*.json"):
        with open(f, 'r', encoding='utf-8') as jf: data = json.load(jf)
        if should_skip(data, f.stem): continue
        sonarr_raw[f.stem] = data
        extract_regex(data.get("specifications", []), raw_patterns_list, "sonarr")

    # Add custom patterns to list for resolution
    for key, pattern in CUSTOM_PATTERNS.items():
        # Support explicit (Title) or (Group) in custom pattern keys
        name = key
        ptype = "Title"
        if " (Title)" in key:
            name = key.replace(" (Title)", "")
            ptype = "Title"
        elif " (Group)" in key:
            name = key.replace(" (Group)", "")
            ptype = "Group"
            
        raw_patterns_list.append({
            "orig_name": name,
            "pattern": pattern,
            "service": "custom",
            "type": ptype
        })

    # Resolve Regex Names
    print("Resolving unique Regex names...")
    resolved_patterns, final_patterns_dict = resolve_regex_names(raw_patterns_list)

    # 2. Second Pass: Convert JSON to CF Dicts using resolved names
    radarr_cfs, sonarr_cfs = {}, {}
    
    print("Converting Radarr Custom Formats...")
    for stem, data in radarr_raw.items():
        radarr_cfs[stem] = convert_cf_to_dict(data, SOURCE_MAPPING["radarr"], stem, resolved_patterns=resolved_patterns)
        
    print("Converting Sonarr Custom Formats...")
    for stem, data in sonarr_raw.items():
        sonarr_cfs[stem] = convert_cf_to_dict(data, SOURCE_MAPPING["sonarr"], stem, resolved_patterns=resolved_patterns)

    # Merge logic
    merged_cfs = {}
    final_cf_names = {} # (service, stem) -> final_name
    all_stems = set(radarr_cfs.keys()) | set(sonarr_cfs.keys())

    print("Merging and Sorting Custom Formats...")
    for stem in all_stems:
        r_cf = radarr_cfs.get(stem)
        s_cf = sonarr_cfs.get(stem)
        
        if r_cf and s_cf:
            r_cond_set = set(str(c) for c in r_cf.get("conditions", []))
            s_cond_set = set(str(c) for c in s_cf.get("conditions", []))
            
            if is_cf_equal(r_cf, s_cf):
                # Identity merge
                merged_cfs[stem] = r_cf
                final_cf_names[("radarr", stem)] = r_cf["name"]
                final_cf_names[("sonarr", stem)] = s_cf["name"]
            elif (r_cond_set.issubset(s_cond_set) or s_cond_set.issubset(r_cond_set)) and not has_incompatible_language(r_cf, s_cf):
                # Easy Merge (Subset) + Language Safe
                merged = fuzzy_merge_cf(r_cf, s_cf)
                merged_cfs[stem] = merged
                final_cf_names[("radarr", stem)] = merged["name"]
                final_cf_names[("sonarr", stem)] = merged["name"]
            else:
                merged = arr_merge_cf(r_cf, s_cf)
                merged_cfs[stem] = merged
                final_cf_names[("radarr", stem)] = merged["name"]
                final_cf_names[("sonarr", stem)] = merged["name"]
        elif r_cf:
            # Radarr only - no collision, no prefix
            merged_cfs[stem] = r_cf
            final_cf_names[("radarr", stem)] = r_cf["name"]
        else:
            # Sonarr only - no collision, no prefix
            merged_cfs[stem] = s_cf
            final_cf_names[("sonarr", stem)] = s_cf["name"]

    # Add custom formats
    for stem, data in CUSTOM_FORMATS.items():
        data["name"] = clean_name(data["name"])
        merged_cfs[stem] = data

    # Remove unwanted release groups from LQ / LQ (Release Title) (by name).
    _lq_remove = {g.lower() for g in LQ_REMOVE_GROUPS}
    for _stem in ("lq", "lq-release-title"):
        if _stem in merged_cfs:
            merged_cfs[_stem]["conditions"] = [
                c for c in merged_cfs[_stem]["conditions"]
                if c.get("name", "").lower() not in _lq_remove
            ]

    # Inject Extra LQ Groups
    print("Injecting Extra LQ Groups into LQ and LQ (Release Title)...")
    if "lq" in merged_cfs:
        for group in EXTRA_LQ_GROUPS:
            # release_group condition -> exact group pattern ^(X)$
            pat_key = (group, f"^({group})$".lower())
            pat_name = resolved_patterns.get(pat_key, group)
            merged_cfs["lq"]["conditions"].append({
                "name": group, "negate": False, "required": False,
                "type": "release_group", "pattern": clean_name(pat_name)
            })
        merged_cfs["lq"]["conditions"] = sort_and_group_conditions(deduplicate_conditions(merged_cfs["lq"]["conditions"]))

    if "lq-release-title" in merged_cfs:
        for group in EXTRA_LQ_GROUPS:
            # release_title condition -> word-boundary substring pattern \b(X)\b
            pat_key = (group, f"\\b({group})\\b".lower())
            pat_name = resolved_patterns.get(pat_key, group)
            merged_cfs["lq-release-title"]["conditions"].append({
                "name": group, "negate": False, "required": False,
                "type": "release_title", "pattern": clean_name(pat_name)
            })
        merged_cfs["lq-release-title"]["conditions"] = sort_and_group_conditions(deduplicate_conditions(merged_cfs["lq-release-title"]["conditions"]))

    return {
        "merged_cfs": merged_cfs,
        "final_patterns_dict": final_patterns_dict,
        "resolved_patterns": resolved_patterns,
        "final_cf_names": final_cf_names,
        "radarr_raw": radarr_raw,
        "sonarr_raw": sonarr_raw,
    }


def build_profiles(guides_dir, model):
    """Build all quality-profile dicts (base + custom copies) in memory.

    Returns (profiles, used_qualities). Shared by the v1 YAML writer and the
    v2 ops emitter. No files are written or read back.
    """
    radarr_raw = model["radarr_raw"]
    sonarr_raw = model["sonarr_raw"]
    final_cf_names = model["final_cf_names"]
    used_qualities = {"radarr": set(), "sonarr": set()}

    profiles = []
    profiles += process_profiles(
        guides_dir / "radarr" / "quality-profiles", radarr_raw, "Radarr",
        None, used_qualities, final_cf_names=final_cf_names)

    sonarr_profile_path = guides_dir / "sonarr" / "quality-profiles"
    for pattern in ["web-1080p.json", "web-1080p-alternative.json",
                    "anime-remux-1080p.json", "web-2160p*.json"]:
        for f in sonarr_profile_path.glob(pattern):
            profiles += process_profiles(
                sonarr_profile_path, sonarr_raw, "Sonarr", None,
                used_qualities, final_cf_names=final_cf_names, specific_file=f)

    by_name = {p["name"]: p for p in profiles}
    copies = []

    def derive(src_name, arr, name_bases, drop_2160p=False):
        src = by_name.get(src_name)
        if not src:
            return
        for name_base in name_bases:
            prefixed = ("(R) " if arr == "Radarr" else "(S) ") + name_base
            new_data = copy.deepcopy(src)
            new_data["name"] = prefixed
            if drop_2160p:
                # Keep the full quality list; disable 2160p instead of removing.
                for q in new_data.get("qualities", []):
                    if "2160p" in q["name"]:
                        q["enabled"] = False
            apply_customizations(new_data, arr, profile_name=prefixed)
            copies.append(new_data)

    derive("(S) WEB-1080p (Alternative)", "Sonarr",
           ["TV (Season Packs)", "TV (Singles)",
            "TV (Season Packs Bypass Dub)", "TV (Singles Bypass Dub)"])
    derive("(R) Remux 2160p (Alternative)", "Radarr",
           ["Movies", "Movies (Bypass Dub)"], drop_2160p=True)
    derive("(R) [Anime] Remux-1080p", "Radarr",
           ["Anime", "Anime (Bypass Dub)"])
    derive("(S) [Anime] Remux-1080p", "Sonarr",
           ["Anime (Season Packs)", "Anime (Singles)",
            "Anime (Season Pack Bypass Dub)", "Anime (Singles Bypass Dub)"])

    return profiles + copies, used_qualities


if __name__ == "__main__":
    print("This module only builds the in-memory model. "
          "Run: python scripts/generate_v2.py")

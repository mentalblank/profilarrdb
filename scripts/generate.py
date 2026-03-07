import json
import yaml
import shutil
from pathlib import Path

from utils.file_utils import clear_output_dirs
from utils.strings import clean_name
from utils.regex_patterns import extract_regex, resolve_regex_names, save_regex_patterns
from utils.custom_formats import (
    convert_cf_to_dict, 
    sort_and_group_conditions, 
    deduplicate_conditions,
    is_cf_equal,
    fuzzy_merge_cf,
    union_merge_cf,
    has_incompatible_language,
    is_union_mergeable
)
from utils.profiles import process_profiles, apply_customizations, should_skip
from utils.media_management import generate_naming_config, generate_quality_definitions
from utils.mappings.source import SOURCE_MAPPING
from utils.mappings.misc import CUSTOM_FORMATS, CUSTOM_PATTERNS, EXTRA_LQ_GROUPS

def main():
    # Check current and parent directory for Guides-master
    guides_root = None
    for prefix in [Path("."), Path("..")]:
        if (prefix / "Guides-master/docs/json").exists():
            guides_root = prefix / "Guides-master/docs/json"
            break
            
    if not guides_root:
        print("Error: Guides-master/docs/json not found!")
        return

    guides_dir = guides_root
    profilarr_dir = Path(".")
    cf_dir, regex_dir, profiles_dir, mm_dir = [
        profilarr_dir / d for d in ["custom_formats", "regex_patterns", "profiles", "media_management"]
    ]

    # Clear existing folders
    clear_output_dirs([cf_dir, regex_dir, profiles_dir, mm_dir])

    # 1. First Pass: Load JSON and Collect all raw patterns
    raw_patterns_list = []
    radarr_raw, sonarr_raw = {}, {}
    
    print("Loading Radarr JSON and collecting patterns...")
    for f in (guides_dir / "radarr" / "cf").glob("*.json"):
        with open(f, 'r') as jf: data = json.load(jf)
        if should_skip(data, f.stem): continue
        radarr_raw[f.stem] = data
        extract_regex(data.get("specifications", []), raw_patterns_list, "radarr")
        
    print("Loading Sonarr JSON and collecting patterns...")
    for f in (guides_dir / "sonarr" / "cf").glob("*.json"):
        with open(f, 'r') as jf: data = json.load(jf)
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
            elif is_union_mergeable(r_cf, s_cf):
                # Union Merge (Only Group/Title lists differ)
                merged = union_merge_cf(r_cf, s_cf)
                merged_cfs[stem] = merged
                final_cf_names[("radarr", stem)] = merged["name"]
                final_cf_names[("sonarr", stem)] = merged["name"]
            else:
                # Different - keep both with prefixes, but synchronize unique groups/titles
                r_new = r_cf.copy()
                s_new = s_cf.copy()
                
                # Identify all unique group/title conditions from both
                r_regex = {c["name"].lower(): c for c in r_cf.get("conditions", []) if c.get("type") in ["release_group", "release_title"]}
                s_regex = {c["name"].lower(): c for c in s_cf.get("conditions", []) if c.get("type") in ["release_group", "release_title"]}
                
                # Synchronize Radarr -> Sonarr
                s_final_conds = s_cf.get("conditions", []).copy()
                for name_l, cond in r_regex.items():
                    if name_l not in s_regex:
                        s_final_conds.append(cond)
                
                # Synchronize Sonarr -> Radarr
                r_final_conds = r_cf.get("conditions", []).copy()
                for name_l, cond in s_regex.items():
                    if name_l not in r_regex:
                        r_final_conds.append(cond)
                
                r_new["conditions"] = sort_and_group_conditions(deduplicate_conditions(r_final_conds))
                s_new["conditions"] = sort_and_group_conditions(deduplicate_conditions(s_final_conds))
                
                r_new["name"] = f"(R) {r_cf['name']}"
                merged_cfs[f"radarr-{stem}"] = r_new
                final_cf_names[("radarr", stem)] = r_new["name"]
                
                s_new["name"] = f"(S) {s_cf['name']}"
                merged_cfs[f"sonarr-{stem}"] = s_new
                final_cf_names[("sonarr", stem)] = s_new["name"]
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

    # Inject Extra LQ Groups
    print("Injecting Extra LQ Groups into LQ and LQ (Release Title)...")
    if "lq" in merged_cfs:
        for group in EXTRA_LQ_GROUPS:
            # Group regex for LQ
            # Use resolved name if it exists (e.g. if it had to be NoRBiT (Group))
            pat_key = (group, f"\\b({group})\\b".lower())
            pat_name = resolved_patterns.get(pat_key, group)
            merged_cfs["lq"]["conditions"].append({
                "name": group, "negate": False, "required": False,
                "type": "release_group", "pattern": clean_name(pat_name)
            })
        merged_cfs["lq"]["conditions"] = sort_and_group_conditions(deduplicate_conditions(merged_cfs["lq"]["conditions"]))

    if "lq-release-title" in merged_cfs:
        for group in EXTRA_LQ_GROUPS:
            # Title regex for LQ (Release Title)
            pat_key = (group, f"^({group})$".lower())
            pat_name = resolved_patterns.get(pat_key, group)
            merged_cfs["lq-release-title"]["conditions"].append({
                "name": group, "negate": False, "required": False,
                "type": "release_title", "pattern": clean_name(pat_name)
            })
        merged_cfs["lq-release-title"]["conditions"] = sort_and_group_conditions(deduplicate_conditions(merged_cfs["lq-release-title"]["conditions"]))

    print(f"Writing {len(merged_cfs)} Custom Formats...")
    for stem, data in merged_cfs.items():
        filename = clean_name(data["name"])
        with open(cf_dir / f"{filename}.yml", 'w') as f:
            yaml.dump(data, f, sort_keys=False)

    # Save Regex Patterns
    save_regex_patterns(final_patterns_dict, regex_dir)

    # Media Management
    generate_naming_config(guides_dir, mm_dir)
    generate_quality_definitions(guides_dir, mm_dir)

    # Processing Quality Profiles
    print("Processing Quality Profiles...")
    used_qualities = {"radarr": set(), "sonarr": set()}
    
    process_profiles(guides_dir / "radarr" / "quality-profiles", radarr_raw, "Radarr", profiles_dir, used_qualities, final_cf_names=final_cf_names)
    
    sonarr_profile_path = guides_dir / "sonarr" / "quality-profiles"
    for pattern in ["web-1080p.json", "web-1080p-alternative.json", "anime-remux-1080p.json", "web-2160p*.json"]:
        for f in sonarr_profile_path.glob(pattern):
            process_profiles(sonarr_profile_path, sonarr_raw, "Sonarr", profiles_dir, used_qualities, final_cf_names=final_cf_names, specific_file=f)

    # Custom Profile Copies (Movies, TV, Anime)
    print("Creating custom profile copies...")
    
    # TV (Season Packs) and TV (Singles)
    source_s = profiles_dir / (clean_name("(S) WEB-1080p (Alternative)") + ".yml")
    if source_s.exists():
        with open(source_s, 'r') as f: s_data = yaml.safe_load(f)
        for name_base in ["TV (Season Packs)", "TV (Singles)", "TV (Season Packs Bypass Dub)", "TV (Singles Bypass Dub)"]:
            prefixed = "(S) " + name_base
            new_data = s_data.copy()
            new_data["name"] = prefixed
            apply_customizations(new_data, "Sonarr", profile_name=prefixed)
            with open(profiles_dir / (clean_name(prefixed) + ".yml"), 'w') as f:
                yaml.dump(new_data, f, sort_keys=False)

    # Movies
    source_r = profiles_dir / (clean_name("(R) Remux 2160p (Alternative)") + ".yml")
    if source_r.exists():
        with open(source_r, 'r') as f: r_data = yaml.safe_load(f)
        for name_base in ["Movies", "Movies (Bypass Dub)"]:
            prefixed = "(R) " + name_base
            new_data = r_data.copy()
            new_data["name"] = prefixed
            new_data["qualities"] = [q for q in r_data.get("qualities", []) if "2160p" not in q["name"]]
            # Fix nested qualities
            for q in new_data["qualities"]:
                if "qualities" in q:
                    q["qualities"] = [nq for nq in q["qualities"] if "2160p" not in nq["name"]]
            apply_customizations(new_data, "Radarr", profile_name=prefixed)
            with open(profiles_dir / (clean_name(prefixed) + ".yml"), 'w') as f:
                yaml.dump(new_data, f, sort_keys=False)

    # Anime (Radarr)
    source_a_r = profiles_dir / (clean_name("(R) [Anime] Remux-1080p") + ".yml")
    if source_a_r.exists():
        with open(source_a_r, 'r') as f: a_data = yaml.safe_load(f)
        for name_base in ["Anime", "Anime (Bypass Dub)"]:
            prefixed = "(R) " + name_base
            new_data = a_data.copy()
            new_data["name"] = prefixed
            apply_customizations(new_data, "Radarr", profile_name=prefixed)
            with open(profiles_dir / (clean_name(prefixed) + ".yml"), 'w') as f:
                yaml.dump(new_data, f, sort_keys=False)

    # Anime (Sonarr)
    source_a_s = profiles_dir / (clean_name("(S) [Anime] Remux-1080p") + ".yml")
    if source_a_s.exists():
        with open(source_a_s, 'r') as f: a_data = yaml.safe_load(f)
        for name_base in ["Anime (Season Packs)", "Anime (Singles)", "Anime (Season Pack Bypass Dub)", "Anime (Singles Bypass Dub)"]:
            prefixed = "(S) " + name_base
            new_data = a_data.copy()
            new_data["name"] = prefixed
            apply_customizations(new_data, "Sonarr", profile_name=prefixed)
            with open(profiles_dir / (clean_name(prefixed) + ".yml"), 'w') as f:
                yaml.dump(new_data, f, sort_keys=False)

    print("Conversion complete!")

if __name__ == "__main__":
    main()

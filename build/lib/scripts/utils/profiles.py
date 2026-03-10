import re
import json
import yaml
from .strings import clean_name, clean_html
from .mappings.misc import ANIME_RENAME_MAPPING
from .mappings.qualities import QUALITY_MAPPING

def should_skip(json_data, stem=""):
    """Check if a custom format or profile should be skipped."""
    name = json_data.get("name", "").lower()
    stem_lower = stem.lower()
    for keyword in ["french", "german", "sqp"]:
        if keyword in name or keyword in stem_lower:
            return True
                
    return False

def apply_customizations(data, tag, profile_name=None):
    """Apply custom profile modifications."""
    # 1. Remove Remuxes
    if "qualities" in data:
        new_qs = []
        for q in data["qualities"]:
            if "Remux" in q["name"]:
                continue
            if "qualities" in q:
                q["qualities"] = [sq for sq in q["qualities"] if "Remux" not in sq["name"]]
                if not q["qualities"]: continue
                # Flatten group if it only has one quality
                if len(q["qualities"]) == 1:
                    original_group_name = q["name"]
                    q = q["qualities"][0]
                    # Update upgrade_until if it was the group
                    if "upgrade_until" in data and data["upgrade_until"].get("name") == original_group_name:
                        data["upgrade_until"] = {"id": q.get("id"), "name": q["name"]}
            new_qs.append(q)
        data["qualities"] = new_qs
    
    # 2. Update upgrade_until if it was a Remux
    if "upgrade_until" in data and "Remux" in data["upgrade_until"].get("name", ""):
        if data["qualities"]:
            data["upgrade_until"] = {"id": data["qualities"][0].get("id"), "name": data["qualities"][0]["name"]}
        else:
            data.pop("upgrade_until", None)

    # 3. Add Custom Formats
    cf_key = "custom_formats_" + tag.lower()
    if cf_key in data:
        # Convert list to dict for easy update
        cf_dict = {item["name"]: item["score"] for item in data[cf_key]}
        cf_dict["Non-Latin Scripts"] = -10000
        cf_dict["Uncensored"] = 1
        cf_dict["x265 (HD)"] = 0
        cf_dict["x265 (no HDR_DV)"] = -10000
        cf_dict["Original Language"] = -10000
        cf_dict["Wrong Language"] = -10000
        cf_dict["Language - Not English"] = 0
        cf_dict["Language - Not Original"] = 0
        cf_dict["Dual-Audio"] = 100

        # Sonarr specific
        if tag.lower() == "sonarr":
            cf_dict["Season Pack"] = 100
            
        # Profile-specific overrides
        if profile_name in ["(S) TV (Season Packs)", "(S) Anime (Season Packs)"]:
            cf_dict["Single Episode"] = -10000
            cf_dict["Multi-Episode"] = -10000

        # Bypass Dub logic
        if profile_name and "Bypass Dub" in profile_name:
            cf_dict["Original Language"] = 0

        # Re-sort
        data[cf_key] = sorted(
            [{"name": k, "score": v} for k, v in cf_dict.items()],
            key=lambda x: (-x["score"], x["name"].lower())
        )

def process_profiles(profile_path, raw_cf_map, tag, profiles_dir, used_qualities, final_cf_names=None, specific_file=None):
    """Convert and save quality profiles."""
    app_tag = tag.lower()
    
    files = [specific_file] if specific_file else profile_path.glob("*.json")
    for json_file in files:
        if json_file.name == "groups.json": continue
        with open(json_file, 'r') as f: data = json.load(f)
        if should_skip(data, json_file.stem): continue
        
        orig_name = data.get("name")
        prefix = "(R) " if tag == "Radarr" else "(S) "
        prefixed_name = prefix + orig_name
        
        profile_yaml = {
            "name": prefixed_name, 
            "description": clean_html(data.get("trash_description", "")), 
            "tags": [tag, "Trash Guides"], 
            "upgradesAllowed": data.get("upgradeAllowed", True),
            "minCustomFormatScore": data.get("minFormatScore", 0), 
            "upgradeUntilScore": data.get("cutoffFormatScore", 10000), 
            "minScoreIncrement": data.get("minUpgradeFormatScore", 1),
            "custom_formats_" + tag.lower(): [], 
            "qualities": [], 
            "language": "must_original"
        }
        
        cf_scores = {} # name -> score
        
        # Identify the score set name
        score_set_name = data.get("trash_score_set")
        
        # 1. First, populate with default scores and overrides from all available CFs
        for stem, cf_raw in raw_cf_map.items():
            # Use the final name from the mapping if provided, otherwise clean the original
            if final_cf_names and (app_tag, stem) in final_cf_names:
                actual_name = final_cf_names[(app_tag, stem)]
            else:
                actual_name = cf_raw.get("name", "").strip()
                if actual_name in ANIME_RENAME_MAPPING:
                    actual_name = ANIME_RENAME_MAPPING[actual_name]
                
                # Always capitalize HULU
                actual_name = re.sub(r'\bHulu\b', 'HULU', actual_name, flags=re.IGNORECASE)
                actual_name = clean_name(actual_name)
                    
            scores = cf_raw.get("trash_scores", {})
            
            # Use profile-specific override if it exists, otherwise use 'default'
            if score_set_name and score_set_name in scores:
                cf_scores[actual_name] = scores[score_set_name]
            elif "default" in scores:
                cf_scores[actual_name] = scores["default"]
        
        # 2. Check formatItems (explicitly listed IDs in the profile)
        format_items = data.get("formatItems", {})
        if format_items:
            for profile_cf_name, cf_id in format_items.items():
                for cf_stem, cf_raw in raw_cf_map.items():
                    if cf_raw.get("trash_id") == cf_id:
                        if final_cf_names and (app_tag, cf_stem) in final_cf_names:
                            actual_name = final_cf_names[(app_tag, cf_stem)]
                        else:
                            actual_name = cf_raw.get("name", "").strip()
                            if actual_name in ANIME_RENAME_MAPPING:
                                actual_name = ANIME_RENAME_MAPPING[actual_name]
                            
                            actual_name = re.sub(r'\bHulu\b', 'HULU', actual_name, flags=re.IGNORECASE)
                            actual_name = clean_name(actual_name)
                        
                        if actual_name not in cf_scores:
                            score = 0
                            if score_set_name and score_set_name in cf_raw.get("trash_scores", {}):
                                score = cf_raw["trash_scores"][score_set_name]
                            else:
                                score = cf_raw.get("trash_scores", {}).get("default", 0)
                            cf_scores[actual_name] = score
                        break

        # Hard overrides
        for override_name in ["Obfuscated", "Retags", "(R) Obfuscated", "(S) Obfuscated"]:
            if override_name in cf_scores:
                cf_scores[override_name] = 0
        
        if "DSNP" in cf_scores:
            cf_scores["HULU"] = cf_scores["DSNP"]
        
        if "CR" in cf_scores:
            cf_scores["HIDIVE"] = cf_scores["CR"]

        if cf_scores:
            profile_yaml["custom_formats_" + tag.lower()] = sorted(
                [{"name": k, "score": v} for k, v in cf_scores.items()],
                key=lambda x: (-x["score"], x["name"].lower())
            )
        
        # Qualities
        raw_items = data.get("items", [])
        processed_items = []
        group_id_counter = -1
        cutoff_name = data.get("cutoff")
        cutoff_item = None

        for item in raw_items:
            if not item.get("allowed", False):
                continue

            q_name = item.get("name")
            q_info = QUALITY_MAPPING.get(q_name.lower(), {"name": q_name})
            target_name = q_info["name"]
            new_item = {"name": target_name}
            
            used_qualities[app_tag].add(target_name)
            
            if "items" in item:
                new_item["id"] = group_id_counter
                new_item["description"] = ""
                group_id_counter -= 1
                
                nested_qualities = []
                for ni in item["items"]:
                    ni_info = QUALITY_MAPPING.get(ni.lower(), {"name": ni})
                    ni_name = ni_info["name"]
                    ni_dict = {"id": ni_info.get("id"), "name": ni_name}
                    nested_qualities.append(ni_dict)
                    used_qualities[app_tag].add(ni_name)
                    if ni_name == cutoff_name:
                        cutoff_item = ni_dict
                new_item["qualities"] = nested_qualities
            else:
                if "id" in q_info:
                    new_item["id"] = q_info["id"]
            
            if target_name == cutoff_name:
                cutoff_item = {"id": new_item.get("id"), "name": target_name}

            processed_items.append(new_item)

        profile_yaml["qualities"] = processed_items
        if cutoff_item:
            profile_yaml["upgrade_until"] = cutoff_item
        
        filename = clean_name(prefixed_name)
        with open(profiles_dir / f"{filename}.yml", 'w') as f:
            yaml.dump(profile_yaml, f, sort_keys=False)

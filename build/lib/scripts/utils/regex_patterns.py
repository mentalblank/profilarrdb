import yaml
from .strings import clean_name

def extract_regex(specifications, patterns_list, service):
    """Collect raw regex patterns from custom format specifications."""
    for spec in specifications:
        impl = spec.get("implementation")
        if impl in ["ReleaseTitleSpecification", "ReleaseGroupSpecification"]:
            name, pattern = spec.get("name"), spec.get("fields", {}).get("value")
            if name and pattern:
                patterns_list.append({
                    "orig_name": name.strip(),
                    "pattern": pattern,
                    "service": service,
                    "type": "Title" if impl == "ReleaseTitleSpecification" else "Group"
                })

def resolve_regex_names(patterns_list):
    """Resolve unique names for all patterns, merging if one is a substring of another."""
    # 1. Group by original name and unique pattern string
    by_name = {}
    for p in patterns_list:
        name = p["orig_name"]
        if name not in by_name:
            by_name[name] = []
        
        exists = False
        for existing in by_name[name]:
            if existing["pattern"].lower() == p["pattern"].lower():
                existing["services"].add(p["service"])
                existing["types"].add(p["type"])
                exists = True
                break
        if not exists:
            by_name[name].append({
                "pattern": p["pattern"],
                "services": {p["service"]},
                "types": {p["type"]}
            })

    # 2. Substring merging logic within each name group
    # (orig_name, pattern_lower) -> survivor_pattern_lower
    absorption_map = {}
    final_by_name = {}
    
    for orig_name, variants in by_name.items():
        # Sort by length descending so we check if shorter patterns are in longer ones
        variants.sort(key=lambda x: len(x["pattern"]), reverse=True)
        
        survivors = []
        for v in variants:
            p_lower = v["pattern"].lower()
            absorbed_by = None
            for s in survivors:
                if p_lower in s["pattern"].lower():
                    absorbed_by = s
                    break
            
            if absorbed_by:
                absorbed_by["services"].update(v["services"])
                absorbed_by["types"].update(v["types"])
                absorption_map[(orig_name, p_lower)] = absorbed_by["pattern"].lower()
            else:
                survivors.append(v)
                absorption_map[(orig_name, p_lower)] = p_lower
        
        final_by_name[orig_name] = survivors

    # 3. Assign final unique names to survivors
    temp_resolved = {} # (orig_name, survivor_pattern_lower) -> final_name
    final_patterns = {} # final_name -> pattern
    
    for orig_name, variants in final_by_name.items():
        if len(variants) == 1:
            final_name = orig_name
            temp_resolved[(orig_name, variants[0]["pattern"].lower())] = final_name
            final_patterns[final_name] = variants[0]["pattern"]
        else:
            all_services = set()
            all_types = set()
            for v in variants:
                all_services.update(v["services"])
                all_types.update(v["types"])
            
            for v in variants:
                suffix = ""
                if len(all_types) > 1 and len(v["types"]) == 1:
                    suffix = f" ({list(v['types'])[0]})"
                
                collision_with_type_only = False
                for other_v in variants:
                    if other_v == v: continue
                    other_suffix = ""
                    if len(all_types) > 1 and len(other_v["types"]) == 1:
                        other_suffix = f" ({list(other_v['types'])[0]})"
                    if other_suffix == suffix:
                        collision_with_type_only = True
                        break
                
                prefix = ""
                if collision_with_type_only and len(all_services) > 1 and len(v["services"]) == 1:
                    s = list(v["services"])[0]
                    prefix = "(R) " if s == "radarr" else "(S) "
                
                candidate = f"{prefix}{orig_name}{suffix}"
                final_name = candidate
                if final_name in final_patterns:
                    counter = 1
                    while f"{candidate} ({counter})" in final_patterns:
                        counter += 1
                    final_name = f"{candidate} ({counter})"
                
                temp_resolved[(orig_name, v["pattern"].lower())] = final_name
                final_patterns[final_name] = v["pattern"]

    # 4. Create final mapping for ALL original patterns (including absorbed ones)
    resolved = {} # (orig_name, pattern_lower) -> final_name
    for (orig_name, p_lower), survivor_p_lower in absorption_map.items():
        resolved[(orig_name, p_lower)] = temp_resolved[(orig_name, survivor_p_lower)]
                
    return resolved, final_patterns

def save_regex_patterns(patterns_dict, output_dir):
    """Save regex patterns to individual YAML files."""
    print(f"Writing {len(patterns_dict)} Regex Patterns...")
    # Sort regex pattern filenames case-insensitively
    sorted_pattern_names = sorted(patterns_dict.keys(), key=lambda x: x.lower())
    for name in sorted_pattern_names:
        pattern = patterns_dict[name]
        cleaned = clean_name(name)
        # Use cleaned name for internal name field too
        regex_data = {
            "name": cleaned,
            "pattern": pattern,
            "description": f"Regex for {name}",
            "tags": ["Trash Guides"],
            "tests": []
        }
        with open(output_dir / f"{cleaned}.yml", 'w') as f:
            yaml.dump(regex_data, f, sort_keys=False)

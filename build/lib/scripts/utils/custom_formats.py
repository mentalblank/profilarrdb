import re
import yaml
from pathlib import Path
from .strings import clean_name, clean_html
from .mappings.source import SOURCE_MAPPING
from .mappings.languages import LANGUAGE_MAPPING
from .mappings.quality_modifiers import QUALITY_MODIFIER_MAPPING
from .mappings.indexer_flags import INDEXER_FLAG_MAPPING
from .mappings.release_type import RELEASE_TYPE_MAPPING
from .mappings.tags import TAG_MAPPING
from .mappings.misc import RESOLUTION_MAPPING, ANIME_RENAME_MAPPING

def get_external_description(stem):
    # Check current and parent directory for Guides-master
    for prefix in [Path("."), Path("..")]:
        desc_path = prefix / "Guides-master/includes/cf-descriptions" / f"{stem}.md"
        if desc_path.exists():
            with open(desc_path, 'r', encoding='utf-8') as f:
                return f.read()
    return None

def convert_cf_to_dict(json_data, source_map, stem, resolved_patterns=None):
    external_desc = get_external_description(stem)
    description = external_desc if external_desc else json_data.get("trash_description", "")
    
    # Strip whitespace from name
    name = json_data.get("name", "").strip()
    if name in ANIME_RENAME_MAPPING:
        name = ANIME_RENAME_MAPPING[name]
    
    # Always capitalize HULU
    name = re.sub(r'\bHulu\b', 'HULU', name, flags=re.IGNORECASE)
    
    name = clean_name(name)

    tags = set(["Trash Guides"])
    conditions = []
    
    for spec in json_data.get("specifications", []):
        spec_name = spec.get("name", "").strip()
        condition = {
            "name": spec_name,
            "negate": spec.get("negate", False),
            "required": spec.get("required", False),
        }
        impl = spec.get("implementation")
        fields = spec.get("fields", {})
        if impl in ["ReleaseTitleSpecification", "ReleaseGroupSpecification"]:
            condition["type"] = "release_title" if impl == "ReleaseTitleSpecification" else "release_group"
            pattern_val = fields.get("value")
            
            # Store raw pattern for merge comparison
            condition["_raw_pattern"] = pattern_val.lower()
            
            # Find the correct name in resolved_patterns that has this pattern_val (case-insensitive)
            final_pattern_name = spec_name
            if resolved_patterns:
                key = (spec_name, pattern_val.lower())
                if key in resolved_patterns:
                    final_pattern_name = resolved_patterns[key]
            
            condition["pattern"] = clean_name(final_pattern_name)
        elif impl == "ResolutionSpecification":
            condition["type"] = "resolution"
            val = fields.get("value")
            condition["resolution"] = RESOLUTION_MAPPING.get(val, f"{val}p" if val else "unknown")
        elif impl == "SourceSpecification":
            condition["type"] = "source"
            val = fields.get("value")
            condition["source"] = source_map.get(val, "unknown")
        elif impl == "LanguageSpecification":
            condition["type"] = "language"
            val = fields.get("value")
            condition["language"] = LANGUAGE_MAPPING["radarr" if "Radarr" in str(source_map) else "sonarr"].get(val, str(val)).lower()
            if "exceptLanguage" in fields:
                condition["exceptLanguage"] = fields["exceptLanguage"]
        elif impl == "QualityModifierSpecification":
            condition["type"] = "quality_modifier"
            val = fields.get("value")
            condition["modifier"] = QUALITY_MODIFIER_MAPPING["radarr" if "Radarr" in str(source_map) else "sonarr"].get(val, str(val))
        elif impl == "IndexerFlagSpecification":
            condition["type"] = "indexer_flag"
            val = fields.get("value")
            condition["flag"] = INDEXER_FLAG_MAPPING["radarr" if "Radarr" in str(source_map) else "sonarr"].get(val, str(val))
        elif impl == "ReleaseTypeSpecification":
            condition["type"] = "release_type"
            val = fields.get("value")
            condition["releaseType"] = RELEASE_TYPE_MAPPING["radarr" if "Radarr" in str(source_map) else "sonarr"].get(val, str(val))
        else:
            condition["type"] = impl.lower().replace("specification", "")
            for k, v in fields.items():
                condition[k] = v
        
        # Add tag based on condition type
        tag_name = TAG_MAPPING.get(condition["type"])
        if tag_name:
            tags.add(tag_name)
            
        conditions.append(condition)

    return {
        "trash_id": json_data.get("trash_id"),
        "name": name,
        "includeCustomFormatWhenRenaming": json_data.get("includeCustomFormatWhenRenaming", False),
        "description": clean_html(description),
        "tags": sorted(list(tags)),
        "conditions": conditions,
        "tests": []
    }

def sort_and_group_conditions(conditions):
    # Sort first by type (grouping) and then by name (case-insensitive alphabetical within group)
    return sorted(conditions, key=lambda x: (str(x.get("type", "") or "").lower(), str(x.get("name", "") or "").lower()))

def deduplicate_conditions(conditions):
    unique_conditions = []
    seen = set()
    for cond in conditions:
        # Exclude internal comparison fields
        cond_clean = {k: v for k, v in cond.items() if not k.startswith("_")}
        cond_tuple = tuple(sorted((k, str(v)) for k, v in cond_clean.items()))
        if cond_tuple not in seen:
            seen.add(cond_tuple)
            unique_conditions.append(cond_clean)
    return unique_conditions

def is_cf_equal(cf1, cf2):
    """Check if two custom format dictionaries are identical in content, ignoring trash_id."""
    # 1. Identity Check
    def clean_cf(cf):
        # Remove metadata and internal comparison fields
        return {k: ([{ck: cv for ck, cv in c.items() if not ck.startswith("_")} for c in v] if k == "conditions" else v) 
                for k, v in cf.items() if k not in ["trash_id", "name"]}
    
    if clean_cf(cf1) != clean_cf(cf2):
        return False
    
    # 2. Language Compatibility Check (even if strings match, source IDs might differ)
    if has_incompatible_language(cf1, cf2):
        return False
        
    return True

def has_incompatible_language(cf1, cf2):
    """Check if two custom formats have conflicting language logic."""
    # Find language conditions
    l1 = [c for c in cf1.get("conditions", []) if c.get("type") == "language"]
    l2 = [c for c in cf2.get("conditions", []) if c.get("type") == "language"]
    
    if not l1 or not l2:
        return False # No language conditions to conflict
        
    # Group by condition name (case-insensitive) to compare specific language logic
    l1_map = {c["name"].lower(): c for c in l1}
    l2_map = {c["name"].lower(): c for c in l2}
    
    shared_names = set(l1_map.keys()) & set(l2_map.keys())
    for name in shared_names:
        c1, c2 = l1_map[name], l2_map[name]
        # If the mapped language string is different, they are incompatible
        if c1.get("language") != c2.get("language"):
            return True
            
    return False

def is_union_mergeable(cf1, cf2):
    """Check if two custom formats only differ by release group/title regex conditions."""
    # 1. Compare non-regex conditions
    r_other = [c for c in cf1.get("conditions", []) if c.get("type") not in ["release_group", "release_title"]]
    s_other = [c for c in cf2.get("conditions", []) if c.get("type") not in ["release_group", "release_title"]]
    
    if len(r_other) != len(s_other):
        return False
        
    # Sort and normalize for comparison (ignore name case)
    def normalize_cond(c):
        # Create a copy and lowercase the name for comparison
        nc = c.copy()
        nc["name"] = nc["name"].lower()
        return str(sorted(nc.items()))

    r_other_set = set(normalize_cond(c) for c in r_other)
    s_other_set = set(normalize_cond(c) for c in s_other)
    
    if r_other_set != s_other_set:
        return False
        
    # 2. Check for conflicting regex names (same name but different pattern)
    # Using case-insensitive keys for name comparison
    r_regex = {c["name"].lower(): c for c in cf1.get("conditions", []) if c.get("type") in ["release_group", "release_title"]}
    s_regex = {c["name"].lower(): c for c in cf2.get("conditions", []) if c.get("type") in ["release_group", "release_title"]}
    
    shared_regex_names = set(r_regex.keys()) & set(s_regex.keys())
    for name in shared_regex_names:
        rp = r_regex[name].get("_raw_pattern", "").lower()
        sp = s_regex[name].get("_raw_pattern", "").lower()
        if rp != sp:
            return False # Same name, different regex logic = conflict
            
    return True

def union_merge_cf(cf1, cf2):
    """Perform a union merge of conditions, combining group/title lists."""
    merged = cf1.copy()
    
    # Combine conditions and deduplicate
    combined_conditions = cf1.get("conditions", []) + cf2.get("conditions", [])
    deduped = deduplicate_conditions(combined_conditions)
    merged["conditions"] = sort_and_group_conditions(deduped)
    
    # Combine tags
    combined_tags = set(cf1.get("tags", [])) | set(cf2.get("tags", []))
    merged["tags"] = sorted(list(combined_tags))
    
    # Use longer description
    desc1 = cf1.get("description", "")
    desc2 = cf2.get("description", "")
    merged["description"] = desc1 if len(desc1) >= len(desc2) else desc2
    
    # Clean name
    name = cf1["name"]
    name = re.sub(r'^\([RS]\) ', '', name)
    merged["name"] = name
    
    return merged

def fuzzy_merge_cf(cf1, cf2):
    """Combine conditions from two custom formats into one merged format."""
    merged = cf1.copy()
    
    # Combine conditions and deduplicate
    combined_conditions = cf1.get("conditions", []) + cf2.get("conditions", [])
    deduped = deduplicate_conditions(combined_conditions)
    merged["conditions"] = sort_and_group_conditions(deduped)
    
    # Combine tags
    combined_tags = set(cf1.get("tags", [])) | set(cf2.get("tags", []))
    merged["tags"] = sorted(list(combined_tags))
    
    # Use longer description
    desc1 = cf1.get("description", "")
    desc2 = cf2.get("description", "")
    merged["description"] = desc1 if len(desc1) >= len(desc2) else desc2
    
    # Remove service prefix from name if present
    name = cf1["name"]
    name = re.sub(r'^\([RS]\) ', '', name)
    merged["name"] = name
    
    return merged

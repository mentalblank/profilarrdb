import json
import yaml
from .mappings.qualities import QUALITY_MAPPING

def generate_naming_config(guides_dir, mm_dir):
    """Generate the naming configuration YAML."""
    print("Updating Naming configurations...")
    radarr_naming_json = guides_dir / "radarr" / "naming" / "radarr-naming.json"
    sonarr_naming_json = guides_dir / "sonarr" / "naming" / "sonarr-naming.json"
    
    radarr_format = ""
    sonarr_standard, sonarr_daily, sonarr_anime = "", "", ""
    
    if radarr_naming_json.exists():
        with open(radarr_naming_json, 'r') as f: rn_data = json.load(f)
        radarr_format = rn_data.get("file", {}).get("standard", "")
    
    if sonarr_naming_json.exists():
        with open(sonarr_naming_json, 'r') as f: sn_data = json.load(f)
        episodes = sn_data.get("episodes", {})
        sonarr_standard = episodes.get("standard", {}).get("default", "")
        sonarr_daily = episodes.get("daily", {}).get("default", "")
        sonarr_anime = episodes.get("anime", {}).get("default", "")
        
    naming_yaml = {
        "radarr": {
            "rename": True, 
            "movieFormat": radarr_format, 
            "movieFolderFormat": "{Movie CleanTitle} ({Release Year}) {tmdb-{TmdbId}}", 
            "replaceIllegalCharacters": True, 
            "colonReplacementFormat": "delete"
        },
        "sonarr": {
            "rename": True, 
            "standardEpisodeFormat": sonarr_standard, 
            "dailyEpisodeFormat": sonarr_daily, 
            "animeEpisodeFormat": sonarr_anime, 
            "seriesFolderFormat": "{Series TitleYear} {tvdb-{TvdbId}}", 
            "seasonFolderFormat": "Season {season:00}", 
            "replaceIllegalCharacters": True, 
            "colonReplacementFormat": 0, 
            "customColonReplacementFormat": "delete", 
            "multiEpisodeStyle": 5
        }
    }
    with open(mm_dir / "naming.yml", 'w') as f:
        yaml.dump(naming_yaml, f, sort_keys=False)

def generate_quality_definitions(guides_dir, mm_dir):
    """Generate the quality definitions YAML."""
    print("Updating Quality Definitions...")
    qd_yaml = {"qualityDefinitions": {"radarr": {}, "sonarr": {}}}
    
    # Load trash-guide values first
    trash_values = {"radarr": {}, "sonarr": {}}
    for tag, qs_file in [("radarr", guides_dir / "radarr" / "quality-size" / "movie.json"), ("sonarr", guides_dir / "sonarr" / "quality-size" / "series.json")]:
        if qs_file.exists():
            with open(qs_file, 'r') as f: data = json.load(f)
            for q in data.get("qualities", []):
                q_name = q["quality"]
                q_info = QUALITY_MAPPING.get(q_name.lower(), {"name": q_name})
                trash_values[tag][q_info["name"]] = q

    # Now populate with ALL qualities from QUALITY_MAPPING
    for tag in ["radarr", "sonarr"]:
        d_min, d_pref, d_max = (1, 1999, 2000) if tag == "radarr" else (5, 995, 1000)
        
        # Sort by ID to keep it consistent
        sorted_map = sorted(QUALITY_MAPPING.items(), key=lambda x: x[1].get("id", 999))
        seen_names = set()
        
        for key, info in sorted_map:
            target_name = info["name"]
            if target_name in seen_names:
                continue
            seen_names.add(target_name)
            
            q_data = trash_values[tag].get(target_name, {})
            qd_yaml["qualityDefinitions"][tag][target_name] = {
                "min": q_data.get("min", d_min),
                "max": q_data.get("max", d_max),
                "preferred": q_data.get("preferred", d_pref)
            }

    with open(mm_dir / "quality_definitions.yml", 'w') as f:
        yaml.dump(qd_yaml, f, sort_keys=False)

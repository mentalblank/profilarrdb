import json
from .mappings.qualities import QUALITY_MAPPING


def build_naming(guides_dir):
    """Build naming config dicts for radarr and sonarr (in memory)."""
    radarr_naming_json = guides_dir / "radarr" / "naming" / "radarr-naming.json"
    sonarr_naming_json = guides_dir / "sonarr" / "naming" / "sonarr-naming.json"

    radarr_format = ""
    sonarr_standard, sonarr_daily, sonarr_anime = "", "", ""

    if radarr_naming_json.exists():
        with open(radarr_naming_json, 'r', encoding='utf-8') as f:
            rn_data = json.load(f)
        radarr_format = rn_data.get("file", {}).get("standard", "")

    if sonarr_naming_json.exists():
        with open(sonarr_naming_json, 'r', encoding='utf-8') as f:
            sn_data = json.load(f)
        episodes = sn_data.get("episodes", {})
        sonarr_standard = episodes.get("standard", {}).get("default", "")
        sonarr_daily = episodes.get("daily", {}).get("default", "")
        sonarr_anime = episodes.get("anime", {}).get("default", "")

    return {
        "radarr": {
            "name": "Radarr",
            "rename": True,
            "movieFormat": radarr_format,
            "movieFolderFormat": "{Movie CleanTitle} ({Release Year}) {tmdb-{TmdbId}}",
            "replaceIllegalCharacters": True,
            "colonReplacementFormat": "delete",
        },
        "sonarr": {
            "name": "Sonarr",
            "rename": True,
            "standardEpisodeFormat": sonarr_standard,
            "dailyEpisodeFormat": sonarr_daily,
            "animeEpisodeFormat": sonarr_anime,
            "seriesFolderFormat": "{Series TitleYear} {tvdb-{TvdbId}}",
            "seasonFolderFormat": "Season {season:00}",
            "replaceIllegalCharacters": True,
            "colonReplacementFormat": 0,
            "customColonReplacementFormat": "delete",
            "multiEpisodeStyle": 5,
        },
    }


def build_quality_definitions(guides_dir):
    """Build quality-definition dicts: {arr: {quality_name: {min,max,preferred}}}."""
    out = {"radarr": {}, "sonarr": {}}

    trash_values = {"radarr": {}, "sonarr": {}}
    for tag, qs_file in [
        ("radarr", guides_dir / "radarr" / "quality-size" / "movie.json"),
        ("sonarr", guides_dir / "sonarr" / "quality-size" / "series.json"),
    ]:
        if qs_file.exists():
            with open(qs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for q in data.get("qualities", []):
                q_name = q["quality"]
                q_info = QUALITY_MAPPING.get(q_name.lower(), {"name": q_name})
                trash_values[tag][q_info["name"]] = q

    # QUALITY_MAPPING is a flat map (key -> {id, name}); collect unique canonical
    # quality names once, ordered by id.
    names = []
    seen = set()
    for _key, info in sorted(QUALITY_MAPPING.items(), key=lambda x: x[1].get("id", 999)):
        name = info["name"]
        if name in seen:
            continue
        seen.add(name)
        names.append(name)

    for tag in ["radarr", "sonarr"]:
        d_min, d_pref, d_max = (1, 1999, 2000) if tag == "radarr" else (5, 995, 1000)
        for name in names:
            q_data = trash_values[tag].get(name, {})
            out[tag][name] = {
                "min": q_data.get("min", d_min),
                "max": q_data.get("max", d_max),
                "preferred": q_data.get("preferred", d_pref),
            }
    return out

"""v2 PCD ops emitter.

Builds a single base seed op file (`ops/0.*.sql`) in the Profilarr v2 / PCD 2.0
format from the in-memory model that generate.py produces (custom formats,
regular expressions, quality profiles). Mirrors the structure of
database-2/ops/0.rosettarr.sql.

Schema reference: profilarr-develop/docs/backend/0.schema.sql
"""

from datetime import datetime, timezone

from .mappings.source import SOURCE_MAPPING

# Per-arr support, from arrSource CustomFormats/Specifications. Used to narrow a
# condition's arr_type so we never target an arr that can't run it.
_RADARR_ONLY_TYPES = {"quality_modifier", "edition", "year"}
_SONARR_ONLY_TYPES = {"release_type"}
_SOURCE_SETS = {
    "radarr": set(SOURCE_MAPPING["radarr"].values()),
    "sonarr": set(SOURCE_MAPPING["sonarr"].values()),
}


def _allowed_arrs(cond):
    """Which arrs can actually run this condition (by type + source value)."""
    ctype = cond.get("type")
    arrs = {"radarr", "sonarr"}
    if ctype in _RADARR_ONLY_TYPES:
        arrs &= {"radarr"}
    if ctype in _SONARR_ONLY_TYPES:
        arrs &= {"sonarr"}
    if ctype == "source":
        src = cond.get("source")
        arrs = {a for a in arrs if src in _SOURCE_SETS[a]}
    return arrs


def resolve_arr_type(cond):
    """Correct a condition's arr_type to match arr capability.

    Narrows 'all' to a single arr when only one supports the condition; honors a
    valid explicit arrType; falls back to the declared value otherwise.
    """
    declared = cond.get("arrType", "all")
    allowed = _allowed_arrs(cond)
    if declared != "all" and declared in allowed:
        return declared
    if len(allowed) == 1:
        return next(iter(allowed))
    if len(allowed) == 2:
        return "all"
    return declared or "all"

# Canonical language names (from profilarr-develop sync/mappings.ts LANGUAGES,
# radarr set = superset). condition_languages.language_name / quality profile
# languages must match these exactly (FK to languages.name).
CANONICAL_LANGUAGES = [
    "Any", "Original", "Unknown", "English", "French", "Spanish", "German",
    "Italian", "Danish", "Dutch", "Japanese", "Icelandic", "Chinese", "Russian",
    "Polish", "Vietnamese", "Swedish", "Norwegian", "Finnish", "Turkish",
    "Portuguese", "Flemish", "Greek", "Korean", "Hungarian", "Hebrew",
    "Lithuanian", "Czech", "Hindi", "Romanian", "Thai", "Bulgarian",
    "Portuguese (Brazil)", "Arabic", "Ukrainian", "Persian", "Bengali",
    "Slovak", "Latvian", "Spanish (Latino)", "Catalan", "Croatian", "Serbian",
    "Bosnian", "Estonian", "Tamil", "Indonesian", "Telugu", "Macedonian",
    "Slovenian", "Malayalam", "Kannada", "Albanian", "Afrikaans", "Marathi",
    "Tagalog", "Urdu", "Romansh", "Mongolian", "Georgian",
]
_LANG_BY_LOWER = {name.lower(): name for name in CANONICAL_LANGUAGES}


def canonical_language(value):
    """Map a (possibly lowercase) language value to its canonical name."""
    if value is None:
        return None
    return _LANG_BY_LOWER.get(str(value).lower(), str(value))


def sql_val(value) -> str:
    """Format a Python value as a SQL literal (matches Profilarr's formatValue)."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


# Map a condition dict (generate.py shape) to (side_table, columns dict) or None.
# Returns the type-specific row to insert alongside the custom_format_conditions row.
def _condition_side(cond):
    ctype = cond.get("type")
    if ctype in ("release_title", "release_group", "edition"):
        # Pattern conditions reference a named regular expression.
        return "condition_patterns", {"regular_expression_name": cond.get("pattern")}
    if ctype == "source":
        return "condition_sources", {"source": cond.get("source")}
    if ctype == "resolution":
        return "condition_resolutions", {"resolution": cond.get("resolution")}
    if ctype == "quality_modifier":
        return "condition_quality_modifiers", {"quality_modifier": cond.get("modifier")}
    if ctype == "indexer_flag":
        return "condition_indexer_flags", {"flag": cond.get("flag")}
    if ctype == "release_type":
        return "condition_release_types", {"release_type": cond.get("releaseType")}
    if ctype == "language":
        return "condition_languages", {
            "language_name": canonical_language(cond.get("language")),
            "except_language": 1 if cond.get("exceptLanguage") else 0,
        }
    if ctype == "size":
        return "condition_sizes", {
            "min_bytes": cond.get("min"),
            "max_bytes": cond.get("max"),
        }
    if ctype == "year":
        return "condition_years", {
            "min_year": cond.get("min"),
            "max_year": cond.get("max"),
        }
    # Unknown / typeless condition: only the base row, no side table.
    return None


class OpsWriter:
    def __init__(self):
        self._sql = []
        self._tags = set()

    # -- low level --------------------------------------------------------
    def _insert(self, table, cols: dict):
        names = ", ".join(cols.keys())
        vals = ", ".join(sql_val(v) for v in cols.values())
        self._sql.append(f"INSERT INTO {table} ({names}) VALUES ({vals});")

    def _tag(self, name):
        """Register a tag (deduplicated; emitted in the header)."""
        if name:
            self._tags.add(name)

    # -- entities ---------------------------------------------------------
    def regular_expression(self, name, pattern, description=None,
                           regex101_id=None, tags=()):
        self._insert("regular_expressions", {
            "name": name,
            "pattern": pattern,
            "regex101_id": regex101_id,
            "description": description,
        })
        for t in tags:
            self._tag(t)
            self._insert("regular_expression_tags", {
                "regular_expression_name": name, "tag_name": t,
            })

    def custom_format(self, name, description, include_in_rename, tags, conditions):
        self._insert("custom_formats", {
            "name": name,
            "description": description or "",
            "include_in_rename": 1 if include_in_rename else 0,
        })
        for t in sorted(set(tags)):
            self._tag(t)
            self._insert("custom_format_tags", {
                "custom_format_name": name, "tag_name": t,
            })
        seen = set()
        for cond in conditions:
            cname = cond.get("name") or cond.get("type") or "condition"
            arr = resolve_arr_type(cond)
            # v2 requires condition names unique per custom format. Collisions
            # arise from the arr-specific remux split (same label, different
            # type/arr_type) and from repeated spec names.
            if cname in seen:
                cand = f"{cname} ({arr})" if arr != "all" else cname
                if cand in seen or cand == cname:
                    i = 2
                    while f"{cname} ({i})" in seen:
                        i += 1
                    cand = f"{cname} ({i})"
                cname = cand
            seen.add(cname)
            self._insert("custom_format_conditions", {
                "custom_format_name": name,
                "name": cname,
                "type": cond.get("type"),
                "arr_type": arr,
                "negate": 1 if cond.get("negate") else 0,
                "required": 1 if cond.get("required") else 0,
            })
            side = _condition_side(cond)
            if side:
                table, extra = side
                row = {"custom_format_name": name, "condition_name": cname}
                row.update(extra)
                self._insert(table, row)

    def quality_profile(self, profile, known_cf_names=None):
        """Emit a quality profile and all its child rows.

        `profile` is a dict in the generate.py shape (name, description, tags,
        upgradesAllowed, minCustomFormatScore, upgradeUntilScore,
        minScoreIncrement, qualities[], upgrade_until, language,
        custom_formats_radarr|custom_formats_sonarr).
        `known_cf_names` (set) gates custom-format scores so we never reference
        a custom format that wasn't emitted (FK safety).
        """
        name = profile["name"]
        arr = "radarr" if "custom_formats_radarr" in profile else "sonarr"

        self._insert("quality_profiles", {
            "name": name,
            "description": profile.get("description") or "",
            "upgrades_allowed": 1 if profile.get("upgradesAllowed", True) else 0,
            "minimum_custom_format_score": profile.get("minCustomFormatScore", 0),
            "upgrade_until_score": profile.get("upgradeUntilScore", 10000),
            "upgrade_score_increment": profile.get("minScoreIncrement", 1) or 1,
        })

        for t in profile.get("tags", []):
            if t == "Trash Guides":
                continue
            self._tag(t)
            self._insert("quality_profile_tags", {
                "quality_profile_name": name, "tag_name": t,
            })

        # Language: values like "must_original", "any". prefix -> type.
        lang = profile.get("language")
        if lang:
            parts = str(lang).split("_", 1)
            if parts[0] in ("must", "only", "not") and len(parts) == 2:
                ltype, lname = parts[0], parts[1]
            else:
                ltype, lname = "simple", lang
            self._insert("quality_profile_languages", {
                "quality_profile_name": name,
                "language_name": canonical_language(lname),
                "type": ltype,
            })

        # Qualities (ordered, complete list). Each item is a single quality or a
        # group; disabled items (enabled=0) are kept so the profile is complete.
        # Reorder so all enabled items sit above all disabled ones (stable within
        # each), matching arr/Profilarr: disabled qualities above the cutoff drop
        # below the enabled block. Preference order among enabled is preserved.
        cutoff = (profile.get("upgrade_until") or {}).get("name")
        raw_items = profile.get("qualities", [])
        items = ([i for i in raw_items if i.get("enabled", True)]
                 + [i for i in raw_items if not i.get("enabled", True)])
        for pos, item in enumerate(items):
            members = item.get("qualities")
            enabled = 1 if item.get("enabled", True) else 0
            # upgrade_until only valid on an enabled item.
            is_cutoff = enabled == 1 and item.get("name") == cutoff
            if members:
                gname = item["name"]
                self._insert("quality_groups", {
                    "quality_profile_name": name, "name": gname,
                })
                for mpos, m in enumerate(members):
                    self._insert("quality_group_members", {
                        "quality_profile_name": name,
                        "quality_group_name": gname,
                        "quality_name": m["name"],
                        "position": mpos,
                    })
                self._insert("quality_profile_qualities", {
                    "quality_profile_name": name,
                    "quality_name": None,
                    "quality_group_name": gname,
                    "position": pos,
                    "enabled": enabled,
                    "upgrade_until": 1 if is_cutoff else 0,
                })
            else:
                self._insert("quality_profile_qualities", {
                    "quality_profile_name": name,
                    "quality_name": item["name"],
                    "quality_group_name": None,
                    "position": pos,
                    "enabled": enabled,
                    "upgrade_until": 1 if is_cutoff else 0,
                })

        # Custom format scores (gated by known CF names for FK safety).
        seen_cf = set()
        skipped = 0
        for entry in profile.get(f"custom_formats_{arr}", []):
            cf = entry.get("name")
            if cf in seen_cf:
                continue
            if known_cf_names is not None and cf not in known_cf_names:
                skipped += 1
                continue
            seen_cf.add(cf)
            self._insert("quality_profile_custom_formats", {
                "quality_profile_name": name,
                "custom_format_name": cf,
                "arr_type": arr,
                "score": entry.get("score", 0),
            })
        return skipped

    # -- media management -------------------------------------------------
    def radarr_naming(self, cfg):
        self._insert("radarr_naming", {
            "name": cfg["name"],
            "rename": 1 if cfg.get("rename", True) else 0,
            "movie_format": cfg.get("movieFormat", ""),
            "movie_folder_format": cfg.get("movieFolderFormat", ""),
            "replace_illegal_characters": 1 if cfg.get("replaceIllegalCharacters") else 0,
            "colon_replacement_format": cfg.get("colonReplacementFormat", "smart"),
        })

    def sonarr_naming(self, cfg):
        self._insert("sonarr_naming", {
            "name": cfg["name"],
            "rename": 1 if cfg.get("rename", True) else 0,
            "standard_episode_format": cfg.get("standardEpisodeFormat", ""),
            "daily_episode_format": cfg.get("dailyEpisodeFormat", ""),
            "anime_episode_format": cfg.get("animeEpisodeFormat", ""),
            "series_folder_format": cfg.get("seriesFolderFormat", ""),
            "season_folder_format": cfg.get("seasonFolderFormat", ""),
            "replace_illegal_characters": 1 if cfg.get("replaceIllegalCharacters") else 0,
            "colon_replacement_format": cfg.get("colonReplacementFormat", 4),
            "custom_colon_replacement_format": cfg.get("customColonReplacementFormat"),
            "multi_episode_style": cfg.get("multiEpisodeStyle", 5),
        })

    def media_settings(self, arr, name, propers_repacks="doNotPrefer",
                       enable_media_info=True):
        table = "radarr_media_settings" if arr == "radarr" else "sonarr_media_settings"
        self._insert(table, {
            "name": name,
            "propers_repacks": propers_repacks,
            "enable_media_info": 1 if enable_media_info else 0,
        })

    def quality_definitions(self, arr, name, entries):
        """entries: {quality_name: {min, max, preferred}}."""
        table = ("radarr_quality_definitions" if arr == "radarr"
                 else "sonarr_quality_definitions")
        for qname, sizes in entries.items():
            self._insert(table, {
                "name": name,
                "quality_name": qname,
                "min_size": sizes.get("min", 0),
                "max_size": sizes.get("max", 0),
                "preferred_size": sizes.get("preferred", 0),
            })

    # -- assemble ---------------------------------------------------------
    def render(self, op_name):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        header = [
            "-- @operation: export",
            "-- @entity: batch",
            f"-- @name: {op_name}",
            f"-- @exportedAt: {ts}",
            "",
            "-- Tags",
        ]
        tag_inserts = [
            f"INSERT INTO tags (name) VALUES ({sql_val(t)});"
            for t in sorted(self._tags)
        ]
        return "\n".join(header + tag_inserts + [""] + self._sql) + "\n"

    def write(self, path, op_name):
        path.write_text(self.render(op_name), encoding="utf-8")

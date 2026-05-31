"""Verify scripts/utils/mappings/* against the actual Radarr/Sonarr source enums.

Parses the C# enums/definitions in arrSource/ and checks our mappings use only
valid arr enum ids and consistent names. Complements check_mappings.py (which
checks against Profilarr's sync/mappings.ts). Read-only.

Usage: python tools_v2/check_arr_source.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from utils.mappings.source import SOURCE_MAPPING
from utils.mappings.indexer_flags import INDEXER_FLAG_MAPPING
from utils.mappings.quality_modifiers import QUALITY_MODIFIER_MAPPING
from utils.mappings.release_type import RELEASE_TYPE_MAPPING
from utils.mappings.languages import LANGUAGE_MAPPING
from utils.mappings.misc import RESOLUTION_MAPPING

ROOT = Path(__file__).resolve().parent.parent
RAD = ROOT / "arrSource/Radarr-develop/src/NzbDrone.Core"
SON = ROOT / "arrSource/Sonarr-5-develop/src/NzbDrone.Core"

problems = []


def parse_enum(text, enum_name):
    """Parse a C# enum body -> {member: int} honoring implicit auto-increment."""
    m = re.search(rf"enum\s+{enum_name}\b.*?\{{(.*?)\}}", text, re.S)
    if not m:
        return {}
    body = m.group(1)
    body = re.sub(r"\[[^\]]*\]", "", body)      # drop attributes
    body = re.sub(r"//.*", "", body)             # drop line comments
    out = {}
    nxt = 0
    for raw in body.split(","):
        raw = raw.strip()
        if not raw:
            continue
        mm = re.match(r"([A-Za-z_]\w*)\s*(=\s*(-?\d+))?", raw)
        if not mm:
            continue
        name = mm.group(1)
        if mm.group(3) is not None:
            nxt = int(mm.group(3))
        out[name] = nxt
        nxt += 1
    return out


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


# Profilarr deliberately renames some arr enum members; treat these as equivalent.
_NAME_ALIASES = {
    "web": "webdl",          # arr QualitySource.Web -> Profilarr web_dl
    "blurayraw": "blurayraw",
}


def names_match(member_norm, name_norm):
    return (member_norm == name_norm
            or _NAME_ALIASES.get(member_norm) == name_norm
            or _NAME_ALIASES.get(name_norm) == member_norm)


def check_ids(label, mine, official_member_to_id, strip_prefixes=()):
    """mine: {id: name}. official: {member: id}. Verify ids valid + names align."""
    id_to_member = {v: k for k, v in official_member_to_id.items()}
    for idv, name in mine.items():
        if idv not in id_to_member:
            problems.append(f"{label}: id {idv} ('{name}') is NOT a valid arr enum value")
            continue
        member = id_to_member[idv]
        for p in strip_prefixes:
            if member.startswith(p):
                member = member[len(p):]
        if not names_match(norm(member), norm(name)):
            problems.append(
                f"{label}: id {idv} = '{name}', arr enum member '{id_to_member[idv]}'")


def main():
    rsrc = (RAD / "Qualities/QualitySource.cs").read_text(encoding="utf-8")
    ssrc = (SON / "Qualities/QualitySource.cs").read_text(encoding="utf-8")
    check_ids("source[radarr]", SOURCE_MAPPING["radarr"], parse_enum(rsrc, "QualitySource"))
    check_ids("source[sonarr]", SOURCE_MAPPING["sonarr"], parse_enum(ssrc, "QualitySource"))

    rmod = (RAD / "Qualities/Modifier.cs").read_text(encoding="utf-8")
    check_ids("quality_modifier[radarr]", QUALITY_MODIFIER_MAPPING["radarr"], parse_enum(rmod, "Modifier"))
    # sonarr has no QualityModifier spec, but our map mirrors remux; validate vs radarr enum
    check_ids("quality_modifier[sonarr]", QUALITY_MODIFIER_MAPPING["sonarr"], parse_enum(rmod, "Modifier"))

    rt = (SON / "Parser/Model/ReleaseType.cs").read_text(encoding="utf-8")
    rt_enum = parse_enum(rt, "ReleaseType")
    for arr in ("radarr", "sonarr"):
        check_ids(f"release_type[{arr}]", RELEASE_TYPE_MAPPING[arr], rt_enum)

    rflag = (RAD / "Parser/Model/IndexerFlags.cs").read_text(encoding="utf-8")
    sflag = (SON / "Parser/Model/IndexerFlags.cs").read_text(encoding="utf-8")
    # Keep PTP_ (Profilarr names them ptp_golden / ptp_approved); strip only G_/AHD_.
    check_ids("indexer_flag[radarr]", INDEXER_FLAG_MAPPING["radarr"],
              parse_enum(rflag, "IndexerFlags"), strip_prefixes=("G_", "AHD_"))
    check_ids("indexer_flag[sonarr]", INDEXER_FLAG_MAPPING["sonarr"],
              parse_enum(sflag, "IndexerFlags"))

    # Resolution: arr Resolution enum values; our produced strings must be 'Np'.
    res = (RAD / "Parser/QualityParser.cs").read_text(encoding="utf-8")
    res_enum = parse_enum(res, "Resolution")
    valid_res = {f"{v}p" for v in res_enum.values() if v > 0}
    for val in RESOLUTION_MAPPING.values():
        if val not in valid_res:
            problems.append(f"resolution: '{val}' not an arr Resolution {sorted(valid_res)}")

    # Languages: arr `new Language(id, "Name")`.
    for arr, base in (("radarr", RAD), ("sonarr", SON)):
        txt = (base / "Languages/Language.cs").read_text(encoding="utf-8")
        official = {int(i): n for i, n in re.findall(r'new Language\((-?\d+),\s*"([^"]+)"\)', txt)}
        for idv, name in LANGUAGE_MAPPING[arr].items():
            if idv not in official:
                problems.append(f"language[{arr}]: id {idv} ('{name}') not in arr Language")
            elif norm(official[idv]) != norm(name):
                problems.append(f"language[{arr}]: id {idv} = '{name}', arr '{official[idv]}'")

    print("Authority: arrSource Radarr/Sonarr C# enums")
    print(f"arr-source mapping problems: {len(problems)}")
    for p in problems:
        print("  ", p)
    return 0 if not problems else 2


if __name__ == "__main__":
    sys.exit(main())

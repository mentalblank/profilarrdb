"""Verify scripts/utils/mappings/* against Profilarr's authority.

Authority = profilarr-develop/src/lib/server/sync/mappings.ts (the enum maps
Profilarr uses to sync to the arr APIs). Parses that file and compares each of
our Python mappings, reporting mismatches. Read-only.

Usage:
    python tools_v2/check_mappings.py
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
from utils.mappings.qualities import QUALITY_MAPPING
from utils.mappings.misc import RESOLUTION_MAPPING

ROOT = Path(__file__).resolve().parent.parent
TS = (ROOT / "profilarr-develop/src/lib/server/sync/mappings.ts").read_text(encoding="utf-8")

problems = []


def block(name):
    """Return the text inside `export const NAME ... = { ... }` (balanced)."""
    m = re.search(rf"export const {name}[^=]*=\s*\{{", TS)
    if not m:
        return ""
    i = m.end() - 1
    depth = 0
    for j in range(i, len(TS)):
        if TS[j] == "{":
            depth += 1
        elif TS[j] == "}":
            depth -= 1
            if depth == 0:
                return TS[i:j + 1]
    return ""


def sub(text, arr):
    m = re.search(rf"{arr}:\s*\{{", text)
    if not m:
        return ""
    i = m.end() - 1
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return ""


def parse_name_num(text):
    """`key: 123` -> {key: 123} (key may be quoted)."""
    out = {}
    for k, v in re.findall(r"['\"]?([A-Za-z0-9_+ ()-]+?)['\"]?\s*:\s*(-?\d+)", text):
        out[k.strip()] = int(v)
    return out


def parse_lang(text):
    """`key: { id: N, name: 'X' }` -> {id: name}."""
    out = {}
    for idv, nm in re.findall(
            r"['\"]?[\w ()]+['\"]?\s*:\s*\{\s*id:\s*(-?\d+),\s*name:\s*'([^']+)'", text):
        out[int(idv)] = nm
    return out


def parse_qual(text):
    """`Key: { id: N, name: 'X', ... }` -> set(names)."""
    return set(re.findall(r"name:\s*'([^']+)'", text))


def check_inverted(label, our, official_name_to_id):
    """our: {id: name}. official: {name: id}. Expect our == invert(official)."""
    expected = {v: k for k, v in official_name_to_id.items()}
    for idv, name in our.items():
        if idv not in expected:
            problems.append(f"{label}: id {idv} ('{name}') not in Profilarr")
        elif expected[idv] != name:
            problems.append(f"{label}: id {idv} = '{name}', Profilarr expects '{expected[idv]}'")
    for idv, name in expected.items():
        if idv not in our:
            problems.append(f"{label}: MISSING id {idv} ('{name}')")


def main() -> int:
    # SOURCES
    src = block("SOURCES")
    for arr in ("radarr", "sonarr"):
        check_inverted(f"source[{arr}]", SOURCE_MAPPING[arr], parse_name_num(sub(src, arr)))

    # INDEXER_FLAGS
    flg = block("INDEXER_FLAGS")
    for arr in ("radarr", "sonarr"):
        check_inverted(f"indexer_flag[{arr}]", INDEXER_FLAG_MAPPING[arr], parse_name_num(sub(flg, arr)))

    # QUALITY_MODIFIERS (flat name->num). Our values must be valid keys.
    qm = parse_name_num(block("QUALITY_MODIFIERS"))
    for arr in ("radarr", "sonarr"):
        for idv, name in QUALITY_MODIFIER_MAPPING[arr].items():
            if name not in qm:
                problems.append(f"quality_modifier[{arr}]: '{name}' not a Profilarr modifier {sorted(qm)}")

    # RELEASE_TYPES
    rt = parse_name_num(block("RELEASE_TYPES"))
    for arr in ("radarr", "sonarr"):
        for idv, name in RELEASE_TYPE_MAPPING[arr].items():
            if name not in rt:
                problems.append(f"release_type[{arr}]: '{name}' not a Profilarr release type {sorted(rt)}")

    # RESOLUTIONS (keys like '1080p'). Our values must be valid keys.
    res_keys = set(parse_name_num(block("RESOLUTIONS")).keys())
    for val in RESOLUTION_MAPPING.values():
        if val not in res_keys:
            problems.append(f"resolution: '{val}' not a Profilarr resolution {sorted(res_keys)}")

    # LANGUAGES: our value.lower() must equal Profilarr name.lower() at same id.
    lng = block("LANGUAGES")
    for arr in ("radarr", "sonarr"):
        official = parse_lang(sub(lng, arr))
        for idv, name in LANGUAGE_MAPPING[arr].items():
            if idv not in official:
                problems.append(f"language[{arr}]: id {idv} ('{name}') not in Profilarr")
            elif official[idv].lower() != str(name).lower():
                problems.append(
                    f"language[{arr}]: id {idv} = '{name}', Profilarr name '{official[idv]}'")
        for idv, name in official.items():
            if idv not in LANGUAGE_MAPPING[arr]:
                problems.append(f"language[{arr}]: MISSING id {idv} ('{name}')")

    # QUALITIES: our names must be valid Profilarr quality names.
    q = block("QUALITIES")
    official_q = parse_qual(sub(q, "radarr")) | parse_qual(sub(q, "sonarr"))
    for info in QUALITY_MAPPING.values():
        if info["name"] not in official_q:
            problems.append(f"quality: '{info['name']}' not a Profilarr quality name")

    print(f"Authority: {(ROOT / 'profilarr-develop/src/lib/server/sync/mappings.ts').name}")
    print(f"Mapping problems: {len(problems)}")
    for p in problems:
        print("  ", p)
    return 0 if not problems else 2


if __name__ == "__main__":
    sys.exit(main())

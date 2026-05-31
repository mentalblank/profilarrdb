"""Heuristic semantic tagging for custom formats.

TRaSH CF JSON carries no tags, so we infer them from the CF name + its
condition types and constrain the result to the official Dictionarry tag
taxonomy (the 60 tags seeded in database-2/ops/0.rosettarr.sql).
"""

import re

# The official tag taxonomy. Anything inferred outside this set is dropped so
# we only ever emit canonical tags.
OFFICIAL_TAGS = {
    "1080p", "2160p", "480p", "576p", "720p", "Anime", "Aspect Ratio", "Audio",
    "Balanced", "Balanced Focused", "Banned", "Bleeding Edge", "Bluray",
    "Channel", "Codec", "Colour Grade", "Compact", "Compact Focused",
    "Container", "DVD", "Dolby", "Dual Audio", "Edition", "Efficient",
    "Efficient Focused", "Encoder", "Enhancement", "Enhancements", "Flag",
    "Freeleech", "GPPi", "Golden Popcorn", "HDR", "HDTV", "HEVC", "Language",
    "Lossless", "Lossless Audio", "Lossy Audio", "Movie", "Preview", "Quality",
    "Quality Focused", "Release Group", "Release Group Tier", "Remux",
    "Remux Focused", "Repack", "Resolution", "SD", "Source", "Storage",
    "Streaming Service", "TV", "UHD Bluray", "WEB-DL", "h264", "h265", "x264",
    "x265",
}

# Baseline tags from condition type.
_TYPE_TAGS = {
    "source": {"Source"},
    "release_group": {"Release Group"},
    "language": {"Language"},
    "edition": {"Edition"},
    "indexer_flag": {"Flag"},
    "quality_modifier": {"Remux", "Source"},  # only remux is used
    "resolution": {"Resolution"},
}

# Resolution value -> tag.
_RES_TAGS = {"2160p": "2160p", "1080p": "1080p", "720p": "720p",
             "576p": "576p", "480p": "480p"}

# Streaming-service abbreviations / names seen in TRaSH CFs.
_STREAMERS = {
    "AMZN", "NF", "DSNP", "HULU", "HMAX", "MAX", "ATVP", "PCOK", "PMTP", "STAN",
    "CRAV", "ALL4", "iP", "MA", "CR", "HIDIVE", "FUNI", "VRV", "ABEMA",
    "BILIBILI", "B-GLOBAL", "OVID", "PARAMOUNT+", "PEACOCK", "APPLE TV+",
    "DISNEY+", "NETFLIX", "SHO", "STARZ", "AUBC", "CBC", "ITV", "BBC",
    "4OD", "RTE", "SKYSHOWTIME", "VDL", "DCU", "QIBI", "QUIBI",
}

# (compiled regex over the CF name, tags). Case-insensitive.
def _rx(p):
    return re.compile(p, re.IGNORECASE)


_NAME_RULES = [
    # Audio
    (_rx(r"\batmos\b"), {"Audio", "Dolby"}),
    (_rx(r"\btrue ?hd\b"), {"Audio", "Dolby", "Lossless Audio"}),
    (_rx(r"\bdts[- ]?hd\b|\bdts[- ]?x\b|\bdts\b"), {"Audio"}),
    (_rx(r"\bdts[- ]?hd ?ma\b"), {"Audio", "Lossless Audio"}),
    (_rx(r"\bdd\+|\bddp\b|\beac3\b|\be-ac-3\b"), {"Audio", "Dolby", "Lossy Audio"}),
    (_rx(r"\bac3\b|\bdolby digital\b|\bdd\b"), {"Audio", "Dolby", "Lossy Audio"}),
    (_rx(r"\baac\b|\bmp3\b|\bopus\b|\bvorbis\b"), {"Audio", "Lossy Audio"}),
    (_rx(r"\bflac\b|\bpcm\b|\blpcm\b"), {"Audio", "Lossless Audio"}),
    (_rx(r"\blossless\b"), {"Audio", "Lossless Audio"}),
    (_rx(r"\bmono\b|\bstereo\b|\bsurround\b|\d\.\d\b"), {"Audio", "Channel"}),
    (_rx(r"dual[- ]?audio"), {"Audio", "Dual Audio"}),
    # Codec
    (_rx(r"\bx265\b"), {"Codec", "x265", "h265", "HEVC"}),
    (_rx(r"\bx264\b"), {"Codec", "x264", "h264"}),
    (_rx(r"\bhevc\b|\bh\.?265\b"), {"Codec", "h265", "HEVC"}),
    (_rx(r"\bavc\b|\bh\.?264\b"), {"Codec", "h264"}),
    (_rx(r"\bav1\b"), {"Codec"}),
    (_rx(r"\b10 ?bit\b|\b8 ?bit\b"), {"Codec"}),
    # HDR
    (_rx(r"\bhdr10\+?\b|\bhdr\b|\bdolby ?vision\b|\bdovi\b|\bdv\b|\bhlg\b|\bpq\b|\bsdr\b"),
     {"HDR"}),
    # Source / quality
    (_rx(r"\bremux\b"), {"Remux", "Source"}),
    (_rx(r"\buhd ?blu[- ]?ray\b"), {"UHD Bluray", "Bluray", "Source"}),
    (_rx(r"\bblu[- ]?ray\b|\bbd\b"), {"Bluray", "Source"}),
    (_rx(r"\bweb[- ]?dl\b|\bweb[- ]?rip\b|\bweb\b"), {"WEB-DL", "Source"}),
    (_rx(r"\bhdtv\b"), {"HDTV", "Source"}),
    (_rx(r"\bdvd\b"), {"DVD", "Source"}),
    (_rx(r"\brepack\b|\bproper\b"), {"Repack"}),
    # Resolution words
    (_rx(r"\b2160p\b|\b4k\b|\buhd\b"), {"2160p", "Resolution"}),
    (_rx(r"\b1080p\b"), {"1080p", "Resolution"}),
    (_rx(r"\b720p\b"), {"720p", "Resolution"}),
    (_rx(r"\b576p\b"), {"576p", "Resolution"}),
    (_rx(r"\b480p\b"), {"480p", "Resolution"}),
    # Edition / aspect
    (_rx(r"\bimax\b"), {"Edition", "Aspect Ratio"}),
    (_rx(r"\bopen ?matte\b|\baspect ratio\b|\b3d\b"), {"Aspect Ratio"}),
    (_rx(r"\bextended\b|\bdirector|\btheatrical\b|\buncut\b|\bunrated\b|\bcriterion\b|\bremaster"),
     {"Edition"}),
    # Tiers / groups
    (_rx(r"\btier\b"), {"Release Group", "Release Group Tier"}),
    # Flags
    (_rx(r"\bfreeleech\b"), {"Freeleech", "Flag"}),
    (_rx(r"\bscene\b|\binternal\b|\bnuked\b"), {"Flag"}),
    # Misc
    (_rx(r"\banime\b"), {"Anime"}),
    (_rx(r"\bgolden ?pop"), {"Golden Popcorn"}),
    (_rx(r"\bcontainer\b|\bmkv\b|\bmp4\b"), {"Container"}),
]


def infer_tags(name, conditions):
    """Return a sorted list of official tags inferred for a custom format."""
    tags = set()

    # 1. From condition types + values.
    for cond in conditions or []:
        ctype = cond.get("type")
        tags |= _TYPE_TAGS.get(ctype, set())
        if ctype == "resolution":
            res = _RES_TAGS.get(cond.get("resolution"))
            if res:
                tags.add(res)

    # 2. From the CF name.
    nm = name or ""
    for rx, rule_tags in _NAME_RULES:
        if rx.search(nm):
            tags |= rule_tags

    # 3. Streaming services (whole-token match against the name).
    upper_tokens = set(re.split(r"[^A-Za-z0-9+]+", nm.upper()))
    if upper_tokens & _STREAMERS or nm.upper() in _STREAMERS:
        tags |= {"Streaming Service", "Source"}

    return sorted(tags & OFFICIAL_TAGS)

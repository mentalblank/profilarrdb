# Resolution value (arr Resolution enum) -> Profilarr resolution string.
# Matches arrSource Parser/QualityParser.Resolution + sync/mappings.ts RESOLUTIONS.
RESOLUTION_MAPPING = {
    2160: "2160p", 1080: "1080p", 720: "720p", 576: "576p",
    540: "540p", 480: "480p", 360: "360p",
}

ANIME_RENAME_MAPPING = {
    "Anime BD Tier 01": "Anime BD Tier 01 (Top SeaDex Muxers)",
    "Anime BD Tier 02": "Anime BD Tier 02 (SeaDex Muxers)",
    "Anime BD Tier 03": "Anime BD Tier 03 (SeaDex Muxers)",
    "Anime BD Tier 04": "Anime BD Tier 04 (SeaDex Muxers)",
    "Anime BD Tier 05": "Anime BD Tier 05 (Remuxes)",
    "Anime BD Tier 06": "Anime BD Tier 06 (FanSubs)",
    "Anime BD Tier 07": "Anime BD Tier 07 (P2P/Scene)",
    "Anime BD Tier 08": "Anime BD Tier 08 (Mini Encodes)",
    "Anime Web Tier 01": "Anime Web Tier 01 (Muxers)",
    "Anime Web Tier 02": "Anime Web Tier 02 (Top FanSubs)",
    "Anime Web Tier 03": "Anime Web Tier 03 (Official Subs)",
    "Anime Web Tier 04": "Anime Web Tier 04 (Official Subs)",
    "Anime Web Tier 05": "Anime Web Tier 05 (FanSubs)",
    "Anime Web Tier 06": "Anime Web Tier 06 (FanSubs)",
}

CUSTOM_PATTERNS = {
    "Non-Latin Scripts": r"[\u4E00-\u9FFF\uAC00-\uD7A3\u0600-\u06FF\u0400-\u04FF\u0370-\u03FF\u0590-\u05FF\u0900-\u097F\u0E00-\u0E7F]",
    "NoRBiT (Title)": r"\b(NoRBiT)\b",
    "NoRBiT (Group)": r"^(NoRBiT)$",
    "PeruGuy (Title)": r"\b(PeruGuy)\b",
    "PeruGuy (Group)": r"^(PeruGuy)$",
    "PortalGoods (Title)": r"\b(PortalGoods)\b",
    "PortalGoods (Group)": r"^(PortalGoods)$",
    "3Li (Title)": r"\b(3Li)\b",
    "3Li (Group)": r"^(3Li)$",
    "MgB (Title)": r"\b(MgB)\b",
    "MgB (Group)": r"^(MgB)$",
    "moviesbyrizzo (Title)": r"\b(moviesbyrizzo)\b",
    "moviesbyrizzo (Group)": r"^(moviesbyrizzo)$",
    "Japhson (Title)": r"\b(Japhson)\b",
    "Japhson (Group)": r"^(Japhson)$",
    "PS3-TEAM (Title)": r"\b(PS3-TEAM)\b",
    "PS3-TEAM (Group)": r"^(PS3-TEAM)$",
    "jeddak (Title)": r"\b(jeddak)\b",
    "jeddak (Group)": r"^(jeddak)$",
    "RIPRARBG (Title)": r"\b(RIPRARBG)\b",
    "RIPRARBG (Group)": r"^(RIPRARBG)$",
    "WinLUNA (Title)": r"\b(WinLUNA)\b",
    "WinLUNA (Group)": r"^(WinLUNA)$",
    "RWP (Title)": r"\b(RWP)\b",
    "RWP (Group)": r"^(RWP)$",
    "NiXON (Title)": r"\b(NiXON)\b",
    "NiXON (Group)": r"^(NiXON)$",
    "SADPANDA (Title)": r"\b(SADPANDA)\b",
    "SADPANDA (Group)": r"^(SADPANDA)$",
    "y2flix (Title)": r"\b(y2flix)\b",
    "y2flix (Group)": r"^(y2flix)$",
    "Gi6 (Title)": r"\b(Gi6)\b",
    "Gi6 (Group)": r"^(Gi6)$",
    "ION10 (Title)": r"\b(ION10)\b",
    "ION10 (Group)": r"^(ION10)$",
    "MIRCrew (Title)": r"\b(MIRCrew)\b",
    "MIRCrew (Group)": r"^(MIRCrew)$",
    "UNTOUCHABLES (Title)": r"\b(UNTOUCHABLES)\b",
    "UNTOUCHABLES (Group)": r"^(UNTOUCHABLES)$",
    "Dual-Audio": r"(dual|multi|funi|eng(lish)?)[\s._-]?(audio|dub(s|bed)?)|[([](dual|multi)[])]|\b([a-zA-Z]{2}\+EN|EN\+[a-zA-Z]{2})\b|\b(\d{3,4}(p|i)|4K|U(ltra)?HD)\b.*\b(DUAL|MULTI)\b(?!.*\(|\))",
}

EXTRA_LQ_GROUPS = [
    "NoRBiT", "PeruGuy", "PortalGoods", "3Li", "MgB", "moviesbyrizzo",
    "Japhson", "PS3-TEAM", "jeddak", "RIPRARBG", "WinLUNA", "RWP",
    "NiXON", "SADPANDA", "y2flix",
    "Gi6", "ION10", "MIRCrew", "UNTOUCHABLES",
]

# Release groups to REMOVE from the LQ and LQ (Release Title) custom formats
# (TRaSH includes them; we drop them). Matched by condition name (case-insensitive).
LQ_REMOVE_GROUPS = ["GalaxyRG", "R&H", "RARBG", "YIFY", "YTS"]

CUSTOM_FORMATS = {
    "non-latin-scripts": {
        "name": "Non-Latin Scripts",
        "includeCustomFormatWhenRenaming": False,
        "description": "Matches releases containing non-Latin scripts (Chinese, Korean, Arabic, Cyrillic, etc.) in the title.",
        "tags": ["Custom", "Release Title", "Language"],
        "conditions": [
            {
                "name": "Non-Latin Scripts",
                "negate": False,
                "required": True,
                "type": "release_title",
                "pattern": "Non-Latin Scripts"
            }
        ],
        "tests": []
    },
    "dual-audio": {
        "name": "Dual-Audio",
        "includeCustomFormatWhenRenaming": False,
        "description": "",
        "tags": ["Custom", "Audio"],
        "conditions": [
            {
                "name": "Dual-Audio",
                "type": "release_title",
                "required": True,
                "negate": False,
                "pattern": "Dual-Audio"
            },
            {
                "name": "English Language",
                "type": "language",
                "required": True,
                "negate": False,
                "language": "english",
                "exceptLanguage": False
            }
        ],
        "tests": []
    },
    "wrong-language": {
        "name": "Wrong Language",
        "includeCustomFormatWhenRenaming": False,
        "description": "",
        "tags": ["Custom", "Language"],
        "conditions": [
            {
                "name": "Not Original",
                "negate": False,
                "required": True,
                "type": "language",
                "language": "original",
                "exceptLanguage": True
            },
            {
                "name": "Not English Language",
                "negate": True,
                "required": True,
                "type": "language",
                "language": "english",
                "exceptLanguage": False
            },
            {
                "name": "Dual-Audio",
                "negate": True,
                "required": True,
                "type": "release_title",
                "pattern": "Dual-Audio"
            }
        ],
        "tests": []
    },
    "original-language": {
        "name": "Original Language",
        "includeCustomFormatWhenRenaming": False,
        "description": "",
        "tags": ["Custom", "Language"],
        "conditions": [
            {
                "name": "Language Original",
                "negate": False,
                "required": True,
                "type": "language",
                "language": "original",
                "exceptLanguage": False
            },
            {
                "name": "Dual-Audio",
                "negate": True,
                "required": False,
                "type": "release_title",
                "pattern": "Dual-Audio"
            },
            {
                "name": "Is English",
                "negate": True,
                "required": True,
                "type": "language",
                "language": "english",
                "exceptLanguage": False
            }
        ],
        "tests": []
    },
}

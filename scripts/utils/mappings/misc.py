RESOLUTION_MAPPING = {
    2160: "2160p", 1080: "1080p", 720: "720p", 576: "576p", 480: "480p",
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
    "NoRBiT (Title)": r"^(NoRBiT)$",
    "NoRBiT (Group)": r"\b(NoRBiT)\b",
    "PeruGuy (Title)": r"^(PeruGuy)$",
    "PeruGuy (Group)": r"\b(PeruGuy)\b",
    "PortalGoods (Title)": r"^(PortalGoods)$",
    "PortalGoods (Group)": r"\b(PortalGoods)\b",
    "3Li (Title)": r"^(3Li)$",
    "3Li (Group)": r"\b(3Li)\b",
    "MgB (Title)": r"^(MgB)$",
    "MgB (Group)": r"\b(MgB)\b",
    "moviesbyrizzo (Title)": r"^(moviesbyrizzo)$",
    "moviesbyrizzo (Group)": r"\b(moviesbyrizzo)\b",
    "Japhson (Title)": r"^(Japhson)$",
    "Japhson (Group)": r"\b(Japhson)\b",
    "PS3-TEAM (Title)": r"^(PS3-TEAM)$",
    "PS3-TEAM (Group)": r"\b(PS3-TEAM)\b",
    "jeddak (Title)": r"^(jeddak)$",
    "jeddak (Group)": r"\b(jeddak)\b",
    "RIPRARBG (Title)": r"^(RIPRARBG)$",
    "RIPRARBG (Group)": r"\b(RIPRARBG)\b",
    "WinLUNA (Title)": r"^(WinLUNA)$",
    "WinLUNA (Group)": r"\b(WinLUNA)\b",
    "RWP (Title)": r"^(RWP)$",
    "RWP (Group)": r"\b(RWP)\b",
    "NiXON (Title)": r"^(NiXON)$",
    "NiXON (Group)": r"\b(NiXON)\b",
    "SADPANDA (Title)": r"^(SADPANDA)$",
    "SADPANDA (Group)": r"\b(SADPANDA)\b",
    "y2flix (Title)": r"^(y2flix)$",
    "y2flix (Group)": r"\b(y2flix)\b",
    "Dual-Audio": r"(dual|multi|funi|eng(lish)?)[\s._-]?(audio|dub(s|bed)?)|[([](dual|multi)[])]|\b([a-zA-Z]{2}\+EN|EN\+[a-zA-Z]{2})\b|\b(\d{3,4}(p|i)|4K|U(ltra)?HD)\b.*\b(DUAL|MULTI)\b(?!.*\(|\))",
}

EXTRA_LQ_GROUPS = [
    "NoRBiT", "PeruGuy", "PortalGoods", "3Li", "MgB", "moviesbyrizzo",
    "Japhson", "PS3-TEAM", "jeddak", "RIPRARBG", "WinLUNA", "RWP",
    "NiXON", "SADPANDA", "y2flix"
]

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

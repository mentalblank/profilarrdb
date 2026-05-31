# SourceSpecification value (arr QualitySource enum id) -> Profilarr source name.
# Inverse of profilarr-develop sync/mappings.ts SOURCES; matches arrSource
# Qualities/QualitySource.cs.
SOURCE_MAPPING = {
    "radarr": {
        1: "cam",
        2: "telesync",
        3: "telecine",
        4: "workprint",
        5: "dvd",
        6: "tv",
        7: "web_dl",
        8: "webrip",
        9: "bluray",
    },
    "sonarr": {
        1: "television",
        2: "television_raw",
        3: "web_dl",
        4: "webrip",
        5: "dvd",
        6: "bluray",
        7: "bluray_raw",
    },
}

# Indexer flag bitmask -> Profilarr flag name.
# Values are the real arr bitmasks (arrSource .../Parser/Model/IndexerFlags.cs);
# names match profilarr-develop sync/mappings.ts INDEXER_FLAGS.
INDEXER_FLAG_MAPPING = {
    "radarr": {
        1: "freeleech",
        2: "halfleech",
        4: "double_upload",
        8: "ptp_golden",
        16: "ptp_approved",
        32: "internal",
        128: "scene",
        256: "freeleech_75",
        512: "freeleech_25",
        2048: "nuked",
    },
    "sonarr": {
        1: "freeleech",
        2: "halfleech",
        4: "double_upload",
        8: "internal",
        16: "scene",
        32: "freeleech_75",
        64: "freeleech_25",
        128: "nuked",
    },
}

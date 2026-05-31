# Profilarr Database (TRaSH Guides Synced)

A [Profilarr](https://dictionarry.dev/)-compliant database, automatically generated from the official [TRaSH Guides](https://trash-guides.info/) for Radarr and Sonarr. Link it in Profilarr v2 to import custom formats, regular expressions, quality profiles, and media-management settings.

## Features

- **Automated Sync**: Rebuilt daily via GitHub Actions from the latest TRaSH Guides JSON.
- **English-Centric**: French, German and SQP custom formats / profiles are excluded.
- **Semantic Tags + Dynamic Quality Sizes**: Heuristic CF tagging and real quality size
  definitions pulled from the guides.

## Repository Structure

- `pcd.json` — PCD manifest (declares the schema dependency + Profilarr min version).
- `ops/0.base.sql` — the generated database (numbered SQL operations).
- `scripts/` — the generator:
  - `generate_v2.py` — entry point (TRaSH Guides → `ops/0.base.sql`).
  - `generate.py` — builds the in-memory model (custom formats, regex, profiles).
  - `utils/` — emitter (`ops_writer.py`), tag rules, and the arr/Profilarr mappings.
- `tools_v2/` — validation tooling (not published as part of the database).

## Automation

`.github/workflows/sync.yml` runs daily (and on manual dispatch): checks out TRaSH Guides, runs `scripts/generate_v2.py`, and commits `ops/` + `pcd.json`.

---
*Note: This database is in active development. Syncing occurs daily at midnight UTC.*

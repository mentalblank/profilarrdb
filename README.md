# Profilarr Database (TRaSH Guides Synced)

This database is automatically synchronized with the official [TRaSH Guides](https://trash-guides.info/) to ensure the most up-to-date and accurate media sourcing configurations for Radarr and Sonarr.

## Features

- **Automated Sync**: Updated daily via GitHub Actions to pull the latest JSON definitions from the TRaSH Guides repository.
- **English-Centric**: Filters out all French and German language custom formats and profiles.
- **Unified Custom Formats**: Identical Sonarr and Radarr custom formats are merged into single files to reduce redundancy.
- **Organized Structure**: All custom format conditions are grouped by type and sorted alphabetically (case-insensitive) for better readability.
- **Standardized Naming**: Automatically syncs naming conventions for Movies, Series, Daily, and Anime releases.
- **Dynamic Quality Sizes**: Pulls real-time quality size definitions from the guides.

## Repository Structure

- `custom_formats/`: Merged YAML definitions for Radarr and Sonarr.
- `regex_patterns/`: Individual regex definitions extracted from the guides.
- `profiles/`: Radarr and Sonarr quality profiles.
- `media_management/`: Naming and quality size configurations.

## Automation

The synchronization is handled by the `convert_trash_to_profilarr.py` script and automated via the GitHub Workflow `.github/workflows/sync.yml`. It performs a full clean of the existing directories before regenerating the YAML files from the source JSON.

---
*Note: This database is in active development. Syncing occurs daily at midnight UTC.*

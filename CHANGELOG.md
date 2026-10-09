# Changelog

## 1.0.1 - 2026-10-10

- Add eight regression tests for snapshot creation, verification, comparison, restoration, and invalid archives.
- Run the suite in GitHub Actions and before packaging tagged releases.
- Include the tests in the downloadable source bundle.

## 1.0.0 — 2026-10-08

- First public release of the local-first desktop and command-line app.
- Added named save-folder profiles, timestamped ZIP snapshots, and per-file SHA-256 manifests.
- Added snapshot verification, added/removed/changed file comparison, and conservative overlay restore with a pre-restore safety snapshot.
- Added archive path validation, duplicate-entry detection, and file-count/uncompressed-size limits.
- Documented save-folder selection, data storage, restore semantics, and limitations.

# Changelog

## 1.1.1 - 2026-10-13

- Reject snapshot manifests with file paths that collide on case-insensitive filesystems before any restore writes occur.
- Add a regression case proving a rejected archive leaves the destination files unchanged.

## 1.1.0 - 2026-10-10

- Compare two live folders by relative path and SHA-256 without changing either folder.
- Print a readable report or JSON for added, removed, changed, and unchanged files.
- Add regression tests for comparison output, equal-size content changes, identical paths, and missing input.

## 1.0.2 - 2026-10-10

- Replace the incomplete v1.0.1 download with a complete source bundle that includes the regression suite.
- Confirm the release archive runs the same regression suite as CI.
- Prevent snapshots created within the same timestamp tick from overwriting one another.
- Add a deterministic regression test for same-timestamp snapshots.

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

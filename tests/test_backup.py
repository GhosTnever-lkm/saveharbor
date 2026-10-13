from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from saveharbor.backup import (
    SnapshotError,
    compare_snapshots,
    compare_folders,
    create_snapshot,
    inspect_snapshot,
    restore_snapshot,
)


class SnapshotWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "saves"
        self.source.mkdir()
        (self.source / "slot1.sav").write_bytes(b"save-one")
        (self.source / "settings").mkdir()
        (self.source / "settings" / "config.ini").write_bytes(b"difficulty=normal\n")
        self.backups = self.root / "backups"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_snapshot_contains_relative_paths_and_verifies_content_hashes(self) -> None:
        created = create_snapshot(self.source, "Example Game", self.backups)
        snapshot = inspect_snapshot(created.archive, verify_files=True)

        self.assertEqual(created.file_count, 2)
        self.assertEqual(snapshot.profile_name, "Example Game")
        self.assertEqual(set(snapshot.files), {"slot1.sav", "settings/config.ini"})
        self.assertEqual(snapshot.total_bytes, len(b"save-one") + len(b"difficulty=normal\n"))
        self.assertEqual(len(snapshot.archive_sha256), 64)

    def test_restore_overlays_verified_files_and_keeps_unlisted_destination_files(self) -> None:
        created = create_snapshot(self.source, "Example Game", self.backups)
        destination = self.root / "restored"
        destination.mkdir()
        (destination / "slot1.sav").write_bytes(b"old-save")
        (destination / "keep.txt").write_text("keep", encoding="utf-8")

        restored = restore_snapshot(created.archive, destination)

        self.assertEqual((destination / "slot1.sav").read_bytes(), b"save-one")
        self.assertEqual((destination / "settings" / "config.ini").read_text(encoding="utf-8"), "difficulty=normal\n")
        self.assertEqual((destination / "keep.txt").read_text(encoding="utf-8"), "keep")
        self.assertEqual(len(restored.files), 2)

    def test_restore_rejects_case_only_paths_before_changing_destination(self) -> None:
        archive = self.root / "case-collision.saveharbor.zip"
        payloads = {"save.sav": b"first-save", "SAVE.sav": b"second-save"}
        manifest = {
            "format": "saveharbor-snapshot",
            "format_version": 1,
            "profile_name": "Example Game",
            "created_at": "2026-10-13T00:00:00+00:00",
            "files": [
                {
                    "path": name,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                for name, data in payloads.items()
            ],
        }
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("manifest.json", json.dumps(manifest))
            for name, data in payloads.items():
                output.writestr(f"files/{name}", data)

        destination = self.root / "restore-destination"
        destination.mkdir()
        existing_save = destination / "save.sav"
        existing_save.write_bytes(b"keep-current-save")
        (destination / "keep.txt").write_text("keep", encoding="utf-8")

        with self.assertRaisesRegex(SnapshotError, "case-insensitive filesystems"):
            restore_snapshot(archive, destination)

        self.assertEqual(existing_save.read_bytes(), b"keep-current-save")
        self.assertEqual((destination / "keep.txt").read_text(encoding="utf-8"), "keep")
        self.assertEqual(sorted(path.name for path in destination.iterdir()), ["keep.txt", "save.sav"])

    def test_compare_reports_added_removed_changed_and_unchanged(self) -> None:
        fixed_time = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        with patch("saveharbor.backup.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = fixed_time
            left = create_snapshot(self.source, "Example Game", self.backups)
            (self.source / "slot1.sav").write_bytes(b"changed-save")
            (self.source / "settings" / "config.ini").unlink()
            (self.source / "new.sav").write_bytes(b"new")
            right = create_snapshot(self.source, "Example Game", self.backups)

        self.assertNotEqual(left.archive, right.archive)

        comparison = compare_snapshots(
            inspect_snapshot(left.archive, verify_files=True),
            inspect_snapshot(right.archive, verify_files=True),
        )

        self.assertEqual(comparison, {
            "added": ["new.sav"],
            "removed": ["settings/config.ini"],
            "changed": ["slot1.sav"],
            "unchanged": [],
        })

    def test_same_timestamp_snapshots_get_distinct_archive_names(self) -> None:
        fixed_time = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        with patch("saveharbor.backup.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = fixed_time
            first = create_snapshot(self.source, "Example Game", self.backups)
            second = create_snapshot(self.source, "Example Game", self.backups)

        self.assertNotEqual(first.archive, second.archive)
        self.assertTrue(first.archive.is_file())
        self.assertTrue(second.archive.is_file())

    def test_verification_rejects_changed_snapshot_file(self) -> None:
        created = create_snapshot(self.source, "Example Game", self.backups)
        rewritten = self.root / "tampered.zip"
        with zipfile.ZipFile(created.archive) as source, zipfile.ZipFile(rewritten, "w") as target:
            for member in source.infolist():
                payload = source.read(member.filename)
                if member.filename == "files/slot1.sav":
                    payload = b"tampered"
                target.writestr(member.filename, payload)

        with self.assertRaisesRegex(SnapshotError, "SHA-256 check failed"):
            inspect_snapshot(rewritten, verify_files=True)

    def test_inspection_rejects_unsafe_manifest_path(self) -> None:
        archive = self.root / "unsafe.zip"
        manifest = {
            "format": "saveharbor-snapshot",
            "format_version": 1,
            "profile_name": "Example",
            "created_at": "2026-10-10T00:00:00+00:00",
            "files": [{"path": "../outside.sav", "size": 1, "sha256": "0" * 64}],
        }
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("manifest.json", json.dumps(manifest))
            output.writestr("files/../outside.sav", b"x")

        with self.assertRaisesRegex(SnapshotError, "unsafe file path"):
            inspect_snapshot(archive)

    def test_inspection_rejects_unlisted_archive_entry(self) -> None:
        created = create_snapshot(self.source, "Example Game", self.backups)
        rewritten = self.root / "extra-entry.zip"
        with zipfile.ZipFile(created.archive) as source, zipfile.ZipFile(rewritten, "w") as target:
            for member in source.infolist():
                target.writestr(member.filename, source.read(member.filename))
            target.writestr("files/unlisted.sav", b"extra")

        with self.assertRaisesRegex(SnapshotError, "unlisted or unexpected"):
            inspect_snapshot(rewritten)

    def test_inspection_rejects_non_saveharbor_zip(self) -> None:
        archive = self.root / "ordinary.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("save.sav", b"data")

        with self.assertRaisesRegex(SnapshotError, "manifest.json is missing"):
            inspect_snapshot(archive)

    def test_empty_source_creates_valid_empty_snapshot(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        result = create_snapshot(empty, "Empty", self.backups)
        snapshot = inspect_snapshot(result.archive, verify_files=True)

        self.assertEqual(result.file_count, 0)
        self.assertEqual(snapshot.files, {})

    def test_compare_folders_reports_added_removed_changed_and_unchanged(self) -> None:
        other = self.root / "other-saves"
        other.mkdir()
        (other / "slot1.sav").write_bytes(b"save-one")
        (other / "new.sav").write_bytes(b"new-save")
        (other / "settings").mkdir()
        (other / "settings" / "config.ini").write_bytes(b"difficulty=hard\n")

        self.assertEqual(compare_folders(self.source, other), {
            "added": ["new.sav"],
            "removed": [],
            "changed": ["settings/config.ini"],
            "unchanged": ["slot1.sav"],
        })

    def test_compare_folders_uses_content_hash_for_equal_size_files(self) -> None:
        other = self.root / "other-saves"
        other.mkdir()
        (other / "slot1.sav").write_bytes(b"SAVE-one")
        (other / "settings").mkdir()
        (other / "settings" / "config.ini").write_bytes(b"difficulty=normal\n")

        comparison = compare_folders(self.source, other)

        self.assertEqual(comparison["changed"], ["slot1.sav"])

    def test_compare_folders_rejects_same_folder(self) -> None:
        with self.assertRaisesRegex(SnapshotError, "two different folders"):
            compare_folders(self.source, self.source)

    def test_compare_folders_rejects_missing_input(self) -> None:
        with self.assertRaises(FileNotFoundError):
            compare_folders(self.source, self.root / "missing")


if __name__ == "__main__":
    unittest.main()

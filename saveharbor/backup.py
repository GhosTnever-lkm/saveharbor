from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable

FORMAT_VERSION = 1
MAX_FILES = 50_000
MAX_TOTAL_BYTES = 20 * 1024 * 1024 * 1024
MAX_FILE_BYTES = 5 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


class SnapshotError(ValueError):
    """Raised when a source folder or snapshot is invalid or unsafe."""


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class Snapshot:
    archive: Path
    profile_name: str
    created_at: str
    files: dict[str, FileRecord]
    total_bytes: int
    archive_sha256: str


@dataclass(frozen=True)
class SnapshotResult:
    archive: Path
    file_count: int
    total_bytes: int
    archive_sha256: str


def _safe_profile_slug(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip(".-_")
    if not slug:
        raise SnapshotError("Profile name must contain at least one letter or number.")
    return slug[:80]


def _walk_files(root: Path) -> Iterable[tuple[Path, str]]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise SnapshotError("The selected save location is not a folder.")
    count = 0
    total = 0
    for directory, dir_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        dir_names[:] = sorted(d for d in dir_names if not (base / d).is_symlink())
        for file_name in sorted(file_names):
            path = base / file_name
            if path.is_symlink() or not path.is_file():
                continue
            try:
                resolved = path.resolve(strict=True)
                rel = resolved.relative_to(root)
                size = path.stat().st_size
            except (OSError, ValueError) as exc:
                raise SnapshotError(f"Could not safely read {path.name}: {exc}") from exc
            if size > MAX_FILE_BYTES:
                raise SnapshotError(f"{rel.as_posix()} exceeds the 5 GB per-file limit.")
            count += 1
            total += size
            if count > MAX_FILES:
                raise SnapshotError(f"Folder exceeds the {MAX_FILES:,} file limit.")
            if total > MAX_TOTAL_BYTES:
                raise SnapshotError("Folder exceeds the 20 GB total size limit.")
            yield path, rel.as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_archive(path: Path) -> str:
    return _sha256_file(path)


def create_snapshot(source: Path, profile_name: str, backup_root: Path) -> SnapshotResult:
    source = source.resolve(strict=True)
    files = list(_walk_files(source))
    now = datetime.now(timezone.utc)
    created = now.replace(microsecond=0).isoformat()
    stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    profile_dir = backup_root / _safe_profile_slug(profile_name)
    profile_dir.mkdir(parents=True, exist_ok=True)
    target = profile_dir / f"{stamp}.saveharbor.zip"
    collision = 1
    while target.exists():
        target = profile_dir / f"{stamp}-{collision}.saveharbor.zip"
        collision += 1
    manifest_files = []
    total = 0
    fd, temp_name = tempfile.mkstemp(prefix=".saveharbor-", suffix=".tmp", dir=profile_dir)
    os.close(fd)
    temp = Path(temp_name)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for file_path, relative in files:
                info = zipfile.ZipInfo(f"files/{relative}")
                info.compress_type = zipfile.ZIP_DEFLATED
                digest = hashlib.sha256()
                size = 0
                with file_path.open("rb") as source, archive.open(info, "w") as output:
                    while chunk := source.read(CHUNK_SIZE):
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                record = {"path": relative, "size": size, "sha256": digest.hexdigest()}
                manifest_files.append(record)
                total += size
            manifest = {
                "format": "saveharbor-snapshot",
                "format_version": FORMAT_VERSION,
                "profile_name": profile_name.strip(),
                "created_at": created,
                "source_label": source.name or str(source),
                "files": manifest_files,
            }
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        os.replace(temp, target)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return SnapshotResult(target, len(manifest_files), total, _hash_archive(target))


def _validated_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise SnapshotError("Snapshot contains an invalid file path.")
    path = PurePosixPath(value)
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if path.is_absolute() or any(
        part in ("", ".", "..")
        or ":" in part
        or part.endswith((".", " "))
        or part.split(".", 1)[0].upper() in reserved
        for part in path.parts
    ):
        raise SnapshotError("Snapshot contains an unsafe file path.")
    return path.as_posix()


def inspect_snapshot(archive_path: Path, verify_files: bool = False, calculate_archive_hash: bool = True) -> Snapshot:
    archive_path = archive_path.resolve(strict=True)
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            members = archive.infolist()
            if len(members) > MAX_FILES + 1:
                raise SnapshotError("Snapshot exceeds the supported file count.")
            names = [member.filename for member in members]
            if len(names) != len(set(names)):
                raise SnapshotError("Snapshot contains duplicate archive paths.")
            if "manifest.json" not in names:
                raise SnapshotError("This ZIP is not a SaveHarbor snapshot: manifest.json is missing.")
            manifest_info = archive.getinfo("manifest.json")
            if manifest_info.file_size > 8 * 1024 * 1024:
                raise SnapshotError("Snapshot manifest is unexpectedly large.")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if not isinstance(manifest, dict) or manifest.get("format") != "saveharbor-snapshot":
                raise SnapshotError("Unrecognized snapshot format.")
            if manifest.get("format_version") != FORMAT_VERSION:
                raise SnapshotError("This snapshot format version is not supported by this SaveHarbor release.")
            profile_name = manifest.get("profile_name")
            created_at = manifest.get("created_at")
            rows = manifest.get("files")
            if not isinstance(profile_name, str) or not isinstance(created_at, str) or not isinstance(rows, list):
                raise SnapshotError("Snapshot manifest is incomplete.")
            file_records: dict[str, FileRecord] = {}
            total = 0
            expected_names = {"manifest.json"}
            for row in rows:
                if not isinstance(row, dict):
                    raise SnapshotError("Snapshot manifest contains an invalid file record.")
                relative = _validated_relative_path(row.get("path"))
                size = row.get("size")
                digest = row.get("sha256")
                if relative in file_records or not isinstance(size, int) or size < 0 or size > MAX_FILE_BYTES:
                    raise SnapshotError("Snapshot manifest contains a duplicate or invalid file record.")
                if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                    raise SnapshotError("Snapshot manifest contains an invalid SHA-256 value.")
                total += size
                if total > MAX_TOTAL_BYTES:
                    raise SnapshotError("Snapshot exceeds the 20 GB uncompressed size limit.")
                member_name = f"files/{relative}"
                expected_names.add(member_name)
                try:
                    info = archive.getinfo(member_name)
                except KeyError as exc:
                    raise SnapshotError(f"Snapshot file is missing: {relative}") from exc
                if info.file_size != size:
                    raise SnapshotError(f"Snapshot size does not match its manifest: {relative}")
                record = FileRecord(relative, size, digest)
                file_records[relative] = record
                if verify_files:
                    actual = hashlib.sha256()
                    with archive.open(info, "r") as stream:
                        while chunk := stream.read(CHUNK_SIZE):
                            actual.update(chunk)
                    if actual.hexdigest() != digest:
                        raise SnapshotError(f"SHA-256 check failed for {relative}.")
            if len(rows) > MAX_FILES:
                raise SnapshotError("Snapshot exceeds the supported file count.")
            if set(names) != expected_names:
                raise SnapshotError("Snapshot contains unlisted or unexpected archive entries.")
            archive_hash = _hash_archive(archive_path) if calculate_archive_hash else ""
            return Snapshot(archive_path, profile_name, created_at, file_records, total, archive_hash)
    except SnapshotError:
        raise
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, RuntimeError) as exc:
        raise SnapshotError(f"Could not read snapshot: {exc}") from exc


def restore_snapshot(archive_path: Path, destination: Path) -> Snapshot:
    snapshot = inspect_snapshot(archive_path, verify_files=True)
    destination = destination.resolve(strict=True)
    if not destination.is_dir():
        raise SnapshotError("Restore destination is not a folder.")
    with tempfile.TemporaryDirectory(prefix="saveharbor-restore-") as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(snapshot.archive, "r") as archive:
            for relative, record in snapshot.files.items():
                target = stage.joinpath(*PurePosixPath(relative).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(f"files/{relative}", "r") as source, target.open("wb") as output:
                    while chunk := source.read(CHUNK_SIZE):
                        output.write(chunk)
                if target.stat().st_size != record.size or _sha256_file(target) != record.sha256:
                    raise SnapshotError(f"Staged file verification failed: {relative}")
        for relative in snapshot.files:
            staged = stage.joinpath(*PurePosixPath(relative).parts)
            target = destination.joinpath(*PurePosixPath(relative).parts)
            parent = target.parent.resolve()
            try:
                parent.relative_to(destination)
            except ValueError as exc:
                raise SnapshotError("Restore path escapes its destination folder.") from exc
            if target.exists() and target.is_dir():
                raise SnapshotError(f"Cannot replace a folder with a save file: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
    return snapshot


def compare_snapshots(left: Snapshot, right: Snapshot) -> dict[str, list[str]]:
    left_paths, right_paths = set(left.files), set(right.files)
    return {
        "added": sorted(right_paths - left_paths),
        "removed": sorted(left_paths - right_paths),
        "changed": sorted(path for path in left_paths & right_paths if left.files[path].sha256 != right.files[path].sha256),
        "unchanged": sorted(path for path in left_paths & right_paths if left.files[path].sha256 == right.files[path].sha256),
    }

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path

from . import __version__
from .backup import create_snapshot, inspect_snapshot, restore_snapshot
from .storage import app_data_dir


def main() -> int:
    parser = argparse.ArgumentParser(prog="saveharbor", description="Local-first game-save backup manager")
    parser.add_argument("--version", action="version", version=f"SaveHarbor {__version__}")
    sub = parser.add_subparsers(dest="command")
    backup = sub.add_parser("backup", help="create a verified snapshot of a save folder")
    backup.add_argument("source", type=Path)
    backup.add_argument("name", help="profile name used to group snapshots")
    verify = sub.add_parser("verify", help="verify a SaveHarbor snapshot archive")
    verify.add_argument("archive", type=Path)
    args = parser.parse_args()

    try:
        if args.command == "backup":
            result = create_snapshot(args.source, args.name, app_data_dir() / "backups")
            print(f"Snapshot created: {result.archive}")
            print(f"Files: {result.file_count}; size: {result.total_bytes:,} bytes; SHA-256: {result.archive_sha256}")
            return 0
        if args.command == "verify":
            snapshot = inspect_snapshot(args.archive, verify_files=True)
            print(f"Verified: {snapshot.profile_name} / {snapshot.created_at}")
            print(f"Files: {len(snapshot.files)}; archive SHA-256: {snapshot.archive_sha256}")
            return 0
    except (OSError, SnapshotError) as exc:
        print(f"SaveHarbor: {exc}", file=sys.stderr)
        return 2

    from .ui import SaveHarborApp

    root = tk.Tk()
    SaveHarborApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

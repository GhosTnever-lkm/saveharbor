from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path

from . import __version__
from .backup import SnapshotError, compare_folders, create_snapshot, inspect_snapshot, restore_snapshot
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
    compare = sub.add_parser("compare-folders", help="compare two folders without changing them")
    compare.add_argument("left", type=Path, help="baseline folder")
    compare.add_argument("right", type=Path, help="folder to compare against the baseline")
    compare.add_argument("--json", action="store_true", help="print the complete report as JSON")
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
        if args.command == "compare-folders":
            result = compare_folders(args.left, args.right)
            if args.json:
                import json

                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                total = sum(map(len, result.values()))
                print(f"Compared folders: {total} distinct relative paths")
                for status in ("added", "removed", "changed", "unchanged"):
                    paths = result[status]
                    print(f"\n{status.title()} ({len(paths)}):")
                    for path in paths:
                        print(f"  {path}")
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

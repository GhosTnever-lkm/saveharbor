from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    directory = Path(base) / "SaveHarbor"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def load_profiles() -> list[dict[str, str]]:
    path = app_data_dir() / "profiles.json"
    if not path.exists():
        return []
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    profiles = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("folder"), str):
            profiles.append({"name": item["name"], "folder": item["folder"]})
    return profiles


def save_profiles(profiles: list[dict[str, str]]) -> None:
    target = app_data_dir() / "profiles.json"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)

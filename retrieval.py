import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KB = ROOT / "knowledge"

def _load(name):
    p = KB / name
    if not p.exists():
        return []
    with p.open() as f:
        return json.load(f)

def lookup(query, osname):
    q = query.lower().strip()

    entries = _load("common.json")

    if osname == "macos":
        entries += _load("macos.json")
    else:
        entries += _load("linux.json")

    # Exact/substring patterns first.
    for item in entries:
        for pattern in item.get("patterns", []):
            if pattern in q:
                return {
                    "source": "knowledge",
                    "id": item["id"],
                    "command": item["command"],
                    "risk": item.get("risk", "unknown"),
                    "auto": item.get("auto", False),
                }

    # Parameterized regex commands.
    for item in entries:
        regex = item.get("regex")
        if not regex:
            continue

        m = re.search(regex, q)
        if not m:
            continue

        values = {}
        if m.groups():
            try:
                values["n"] = max(1, min(int(m.group(1)), 100))
            except (ValueError, TypeError):
                pass

        command = item["command"].format(**values)

        return {
            "source": "knowledge",
            "id": item["id"],
            "command": command,
            "risk": item.get("risk", "unknown"),
            "auto": item.get("auto", False),
        }

    return None

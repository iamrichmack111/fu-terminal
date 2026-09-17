#!/usr/bin/env python3

import json
import time
import urllib.request
from pathlib import Path

OUT = Path("knowledge/sources/commandlinefu.json")
BASE = "https://www.commandlinefu.com/commands/browse/sort-by-votes/json/{}"

all_commands = {}
offset = 0
page_size = 25

while True:
    url = BASE.format(offset)
    print(f"Fetching offset {offset} ...", flush=True)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "FU-Terminal-Assistant/1.0"}
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            page = json.load(r)
    except Exception as e:
        print("Fetch stopped:", e)
        break

    if not page:
        print("No more results.")
        break

    added = 0

    for item in page:
        command = (item.get("command") or "").strip()

        if not command:
            continue

        if command not in all_commands:
            all_commands[command] = {
                "id": item.get("id"),
                "command": command,
                "summary": (item.get("summary") or "").strip(),
                "votes": item.get("votes", 0),
                "url": item.get("url"),
            }
            added += 1

    print(
        f"  received={len(page)} "
        f"new={added} "
        f"total={len(all_commands)}"
    )

    if len(page) < page_size:
        break

    offset += page_size

    # Don't hammer the service.
    time.sleep(0.20)

OUT.write_text(
    json.dumps(
        list(all_commands.values()),
        indent=2,
        ensure_ascii=False
    ) + "\n"
)

print()
print("Saved:", OUT)
print("Unique commands:", len(all_commands))

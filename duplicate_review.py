#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path

CACHE = (
    Path.home()
    / "Desktop"
    / "FU-Workspace"
    / "sessions"
    / "duplicate-results.json"
)

GENERATED_HINTS = (
    "/.demo-voices/",
    "/public/",
    "/songs/",
    "/tracks/",
    "/dance/",
)

def human(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    n = float(n)

    for unit in units:
        if n < 1024 or unit == units[-1]:
            return f"{n:.1f} {unit}"
        n /= 1024

if not CACHE.exists():
    print("FU duplicate cache not found.")
    print()
    print('Run:')
    print('  fu --auto "find duplicate files in Downloads"')
    sys.exit(2)

try:
    data = json.loads(CACHE.read_text())
except Exception as e:
    print(f"FU could not read duplicate cache: {e}")
    sys.exit(2)

age = time.time() - data.get("created", 0)

# Avoid acting on ancient filesystem information.
if age > 3600:
    print(f"FU duplicate cache is {age/60:.0f} minutes old.")
    print()
    print('Refresh it with:')
    print('  fu --auto "find duplicate files in Downloads"')
    sys.exit(2)

groups = []

for group in data.get("groups", []):
    paths = [Path(x) for x in group.get("paths", [])]

    if len(paths) < 2:
        continue

    # Make sure cached files still exist.
    existing = [p for p in paths if p.exists()]

    if len(existing) < 2:
        continue

    score = sum(
        any(hint in str(p) for hint in GENERATED_HINTS)
        for p in existing
    )

    reclaim = group.get(
        "reclaimable",
        group.get("size", 0) * (len(existing) - 1)
    )

    groups.append(
        (
            score,
            reclaim,
            group.get("size", 0),
            existing
        )
    )

groups.sort(
    key=lambda x: (x[0], x[1]),
    reverse=True
)

print()
print("◆ FU DUPLICATE REVIEW")
print("─" * 72)
print()
print("READ ONLY — using verified results from the previous duplicate scan.")
print(f"Cache age: {age:.1f}s")
print()
print("These are REVIEW candidates, not automatic deletion targets.")
print()

shown = 0
total = 0

for score, reclaim, size, paths in groups:
    if score == 0:
        continue

    shown += 1
    total += reclaim

    print(
        f"{shown:>2}. REVIEW · "
        f"{len(paths)} identical copies · "
        f"{human(reclaim)} potentially reclaimable"
    )

    for path in paths[:6]:
        print(f"    {path}")

    if len(paths) > 6:
        print(f"    ... +{len(paths)-6} more")

    print()

    if shown >= 15:
        break

print("─" * 72)
print(f"Review groups shown : {shown}")
print(f"Potential space     : {human(total)}")
print()
print("FU has NOT selected a copy to delete.")
print("FU has NOT deleted or modified anything.")

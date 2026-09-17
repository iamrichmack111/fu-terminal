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

def human(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    n = float(n)
    for u in units:
        if n < 1024 or u == units[-1]:
            return f"{n:.1f} {u}"
        n /= 1024

def path_score(p):
    """
    Higher score = stronger KEEP candidate.
    This is deliberately conservative.
    """
    s = str(p).lower()
    score = 0
    reasons = []

    # Prefer directories that look like primary/current projects.
    if "/main/" in s or s.endswith("-main"):
        score += 4
        reasons.append("main project path")

    if "/final/" in s or "-final/" in s:
        score += 3
        reasons.append("final project path")

    if "/git/" in s or "-git/" in s:
        score += 2
        reasons.append("Git/project path")

    # Deprioritize obvious tests/copies/variants.
    penalties = {
        "test": -4,
        "backup": -4,
        "copy": -3,
        "old": -3,
        "remaining": -2,
        "purple": -1,
        "voicefix": -1,
    }

    for word, points in penalties.items():
        if word in s:
            score += points
            reasons.append(f"{word} path")

    return score, reasons

if not CACHE.exists():
    print("FU duplicate cache not found.")
    print('Run: fu --auto "find duplicate files in Downloads"')
    sys.exit(2)

data = json.loads(CACHE.read_text())
age = time.time() - data.get("created", 0)

if age > 3600:
    print(f"FU duplicate cache is {age/60:.0f} minutes old.")
    print('Refresh: fu --auto "find duplicate files in Downloads"')
    sys.exit(2)

plans = []

for group in data.get("groups", []):
    paths = [Path(x) for x in group.get("paths", [])]
    paths = [p for p in paths if p.exists()]

    if len(paths) < 2:
        continue

    scored = []

    for p in paths:
        score, reasons = path_score(p)
        scored.append((score, p, reasons))

    scored.sort(key=lambda x: (-x[0], len(str(x[1])), str(x[1])))

    keep_score, keep, keep_reasons = scored[0]
    remove = [x[1] for x in scored[1:]]

    # Confidence depends on whether one path clearly outranks the others.
    scores = [x[0] for x in scored]

    if len(scores) > 1 and scores[0] >= scores[1] + 4:
        confidence = "HIGH"
    elif len(scores) > 1 and scores[0] > scores[1]:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    reclaim = group.get("size", 0) * len(remove)

    plans.append({
        "keep": keep,
        "remove": remove,
        "reclaim": reclaim,
        "confidence": confidence,
        "reason": ", ".join(keep_reasons) if keep_reasons else
                  "no authoritative project path could be determined"
    })

# Largest potential savings first.
plans.sort(key=lambda x: x["reclaim"], reverse=True)

print()
print("◆ FU DUPLICATE CLEANUP PLAN")
print("─" * 76)
print()
print("READ ONLY — this is a proposed plan. Nothing will be deleted.")
print(f"Cache age: {age:.1f}s")
print()

shown = 0
total = 0

for plan in plans:
    if shown >= 15:
        break

    shown += 1
    total += plan["reclaim"]

    print(
        f"{shown:>2}. {plan['confidence']:<6} · "
        f"{human(plan['reclaim'])} potentially reclaimable"
    )

    print("    KEEP")
    print(f"      {plan['keep']}")

    print("    REMOVE CANDIDATES")
    for p in plan["remove"][:6]:
        print(f"      {p}")

    if len(plan["remove"]) > 6:
        print(f"      ... +{len(plan['remove']) - 6} more")

    print(f"    REASON: {plan['reason']}")
    print()

print("─" * 76)
print(f"Groups planned     : {shown}")
print(f"Potential reclaim  : {human(total)}")
print()
print("IMPORTANT:")
print("LOW/MEDIUM confidence means FU cannot prove which project copy")
print("is authoritative. Review those groups before any deletion.")
print()
print("No rm command was generated.")
print("No files were modified.")

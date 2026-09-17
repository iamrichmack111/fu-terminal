#!/usr/bin/env python3
import os
import json
import sys
import hashlib
import time
from pathlib import Path
from collections import defaultdict

ROOT = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / "Downloads"

SKIP = {
    "node_modules", ".venv", "venv", ".demo-venv", ".venv-playwright",
    ".voice-venv", ".git", "__pycache__", ".cache", "dist", "build"
}

C = {
    "cyan": "\033[96m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "gray": "\033[90m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}

tty = sys.stdout.isatty()

def color(s, name):
    return f"{C[name]}{s}{C['reset']}" if tty else s

def human(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    n = float(n)
    for u in units:
        if n < 1024 or u == "TB":
            return f"{n:.1f} {u}"
        n /= 1024

def bar(label, current, total, width=28):
    if not tty:
        return
    total = max(total, 1)
    ratio = min(current / total, 1)
    done = int(width * ratio)
    b = "█" * done + "░" * (width - done)
    print(
        f"\r{color('◆','cyan')} {label:<17} "
        f"{color(b,'cyan')} {int(ratio*100):3d}%",
        end="",
        flush=True
    )

print()
print(color("◆ FU DUPLICATE SCANNER", "bold"))
print(color("─" * 72, "gray"))
print(f"Target : {ROOT}")
print("Ignore : dependency, virtualenv, cache, build and Git directories")
print()

started = time.perf_counter()

# ── Stage 1: scan metadata ─────────────────────────────────────
sizes = defaultdict(list)
files_seen = 0

for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]

    for name in files:
        p = Path(base) / name
        try:
            size = p.stat().st_size
        except OSError:
            continue

        if size <= 0:
            continue

        sizes[size].append(p)
        files_seen += 1

print(color("✓", "green"), f"Scanned {files_seen:,} files")

# ── Stage 2: only same-size candidates ─────────────────────────
groups = [x for x in sizes.values() if len(x) > 1]
candidates = [p for group in groups for p in group]

print(
    color("✓", "green"),
    f"Reduced to {len(candidates):,} same-size candidates"
)

# ── Stage 3: quick fingerprint ─────────────────────────────────
quick = defaultdict(list)

for i, p in enumerate(candidates, 1):
    try:
        size = p.stat().st_size

        with p.open("rb") as f:
            first = f.read(65536)

            if size > 65536:
                f.seek(max(0, size - 65536))
                last = f.read(65536)
            else:
                last = b""

        h = hashlib.blake2b(digest_size=16)
        h.update(first)
        h.update(last)

        quick[(size, h.digest())].append(p)

    except OSError:
        pass

    if i % 25 == 0 or i == len(candidates):
        bar("Fingerprinting", i, len(candidates))

if tty and candidates:
    print()

full_candidates = [
    p
    for paths in quick.values()
    if len(paths) > 1
    for p in paths
]

print(
    color("✓", "green"),
    f"Only {len(full_candidates):,} require full hashing"
)

# ── Stage 4: full hash only likely duplicates ──────────────────
final = defaultdict(list)

for i, p in enumerate(full_candidates, 1):
    try:
        size = p.stat().st_size
        h = hashlib.blake2b(digest_size=16)

        with p.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)

        final[(size, h.digest())].append(p)

    except OSError:
        pass

    if i % 5 == 0 or i == len(full_candidates):
        bar("Verifying", i, len(full_candidates))

if tty and full_candidates:
    print()

duplicates = [
    (size, paths)
    for (size, _), paths in final.items()
    if len(paths) > 1
]

duplicates.sort(
    key=lambda x: x[0] * (len(x[1]) - 1),
    reverse=True
)

# Save verified duplicate results for FU follow-ups.
cache_file = (
    Path.home()
    / "Desktop"
    / "FU-Workspace"
    / "sessions"
    / "duplicate-results.json"
)

cache_file.parent.mkdir(parents=True, exist_ok=True)

cache_data = {
    "root": str(ROOT),
    "created": time.time(),
    "groups": [
        {
            "size": size,
            "paths": [str(path) for path in paths],
            "reclaimable": size * (len(paths) - 1)
        }
        for size, paths in duplicates
    ]
}

tmp_cache = cache_file.with_suffix(".tmp")
tmp_cache.write_text(json.dumps(cache_data, indent=2))
tmp_cache.replace(cache_file)

wasted = sum(
    size * (len(paths) - 1)
    for size, paths in duplicates
)

elapsed = time.perf_counter() - started

print()
print(color("─" * 72, "gray"))
print(color("RESULTS", "bold"))
print()
print(f"Duplicate groups : {len(duplicates):,}")
print(f"Potential saving : {color(human(wasted), 'green')}")
print(f"Scan time        : {elapsed:.2f}s")

if not duplicates:
    sys.exit(0)

print()
print(color("Largest duplicate groups", "bold"))
print()

for num, (size, paths) in enumerate(duplicates[:15], 1):
    reclaim = size * (len(paths) - 1)

    print(
        color(f"{num:>2}.", "cyan"),
        f"{len(paths)} copies · {human(size)} each · "
        f"{color(human(reclaim), 'yellow')} reclaimable"
    )

    for p in paths[:6]:
        print("    ", p)

    if len(paths) > 6:
        print(color(f"     … +{len(paths)-6} more", "gray"))

    print()

#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path

def human(n):
    units = ["B","KB","MB","GB","TB"]
    n = float(n)
    for u in units:
        if n < 1024 or u == units[-1]:
            return f"{n:.1f} {u}"
        n /= 1024

parser = argparse.ArgumentParser()
parser.add_argument("path")
args = parser.parse_args()

root = Path(args.path).expanduser().resolve()

if not root.exists():
    raise SystemExit(f"Path does not exist: {root}")

print()
print("◆ FU STORAGE ANALYZER")
print("─" * 76)
print(f"TARGET: {root}")
print("READ ONLY — nothing will be removed.")
print()

# Largest immediate children
print("LARGEST DIRECTORIES")
print("─" * 76)

try:
    p = subprocess.run(
        ["du", "-x", "-d", "1", "-B1", str(root)],
        text=True,
        capture_output=True,
        timeout=30
    )

    rows = []

    for line in p.stdout.splitlines():
        try:
            size, path = line.split("\t", 1)
            path = Path(path)

            if path.resolve() != root:
                rows.append((int(size), path))
        except Exception:
            pass

    rows.sort(key=lambda x: x[0], reverse=True)

    for size, path in rows[:20]:
        print(f"{human(size):>10}  {path}")

except subprocess.TimeoutExpired:
    print("Scan exceeded 30 seconds.")
    rows = []

print()
print("LARGEST FILES")
print("─" * 76)

files = []

try:
    p = subprocess.Popen(
        ["find", str(root), "-xdev", "-type", "f", "-printf", "%s\t%p\n"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True
    )

    for line in p.stdout:
        try:
            size, path = line.rstrip("\n").split("\t", 1)
            size = int(size)

            files.append((size, path))

            # Keep memory bounded.
            if len(files) > 5000:
                files.sort(reverse=True)
                files = files[:1000]

        except Exception:
            pass

    p.wait(timeout=30)

except Exception:
    pass

files.sort(reverse=True)

for size, path in files[:25]:
    print(f"{human(size):>10}  {path}")

print()
print("─" * 76)

if files:
    print(f"Largest file: {human(files[0][0])}")
    print(f"Path: {files[0][1]}")

print()
print("FU has NOT deleted or modified anything.")

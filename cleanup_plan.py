#!/usr/bin/env python3
import shutil
import subprocess
from pathlib import Path

def root_df():
    """Return df-compatible root filesystem totals and percentage."""
    import subprocess
    p = subprocess.run(
        ["df", "-B1", "--output=size,used,avail,pcent", "/"],
        text=True,
        capture_output=True,
        timeout=5,
        check=True,
    )
    line = p.stdout.strip().splitlines()[-1].split()
    return {
        "total": int(line[0]),
        "used": int(line[1]),
        "avail": int(line[2]),
        "pct": float(line[3].rstrip("%")),
    }


HOME = Path.home()

def human(n):
    units = ["B","KB","MB","GB","TB"]
    n = float(n)
    for u in units:
        if n < 1024 or u == units[-1]:
            return f"{n:.1f} {u}"
        n /= 1024

def du(path):
    path = Path(path)
    if not path.exists():
        return 0

    try:
        p = subprocess.run(
            ["du", "-sx", "-B1", str(path)],
            text=True,
            capture_output=True,
            timeout=10
        )
        if p.stdout:
            return int(p.stdout.split("\t",1)[0])
    except Exception:
        pass

    return 0

usage = root_df()

candidates = [
    (
        "pip cache",
        HOME / ".cache/pip",
        "HIGH",
        "pip cache purge"
    ),
    (
        "Chrome cache",
        HOME / ".cache/google-chrome",
        "HIGH",
        "rm -rf \"$HOME/.cache/google-chrome\""
    ),
    (
        "Playwright browsers",
        HOME / ".cache/ms-playwright",
        "MEDIUM",
        "rm -rf \"$HOME/.cache/ms-playwright\""
    ),
]

rows = []

for name, path, confidence, command in candidates:
    size = du(path)

    if size:
        rows.append({
            "name": name,
            "path": path,
            "size": size,
            "confidence": confidence,
            "command": command
        })

high = sum(
    r["size"]
    for r in rows
    if r["confidence"] == "HIGH"
)

high_medium = sum(r["size"] for r in rows)

projected_high_used = max(0, usage["used"] - high)
projected_high_avail = usage["avail"] + high

projected_all_used = max(0, usage["used"] - high_medium)
projected_all_avail = usage["avail"] + high_medium

projected_high_pct = (
    projected_high_used /
    (projected_high_used + projected_high_avail) * 100
)

projected_all_pct = (
    projected_all_used /
    (projected_all_used + projected_all_avail) * 100
)

print()
print("◆ FU CLEANUP PLAN")
print("─" * 88)
print("PLAN ONLY — nothing will be deleted.")
print()

print("CURRENT")
print(f"  Used                 {human(usage['used'])}")
print(f"  Available            {human(usage['avail'])}")
print(f"  Root usage           {usage['pct']:.1f}%  [df authoritative]")
print()

print("HEALTH STATUS")
print("─" * 88)

if usage["pct"] >= 90:
    print("  ATTENTION — filesystem usage is high.")
    print("  Review reclaim opportunities before removing anything.")
elif usage["pct"] >= 85:
    print("  WATCH — filesystem usage is elevated but not critical.")
    print("  Cleanup may be useful soon.")
else:
    print("  HEALTHY — no cleanup is required for filesystem health.")
    print("  The candidates below are optional reclaim opportunities.")

print()

print("CANDIDATES")
print("─" * 88)

for row in rows:
    print(
        f"  {human(row['size']):>10}  "
        f"{row['confidence']:<7} "
        f"{row['name']}"
    )
    print(f"              {row['path']}")
    print()

print("PROJECTED")
print("─" * 88)

print(f"  HIGH only reclaim    {human(high)}")
print(f"  Projected usage      ~{projected_high_pct:.1f}%  [estimate]")
print()

print(f"  HIGH + MEDIUM        {human(high_medium)}")
print(f"  Projected usage      ~{projected_all_pct:.1f}%  [estimate]")
print()

print("COMMANDS — NOT EXECUTED")
print("─" * 88)

for row in rows:
    print(f"  [{row['confidence']}] {row['command']}")

print()
print("REVIEW-ONLY LARGE STORAGE")
print("─" * 88)

review_paths = [
    (
        "System Ollama models",
        Path("/usr/share/ollama/.ollama/models"),
        "Use `ollama list` / `ollama rm MODEL`; never delete blobs directly."
    ),
    (
        "Snap Docker data",
        Path("/var/snap/docker/common/var-lib-docker"),
        "Verify whether the disabled Snap Docker store is stale before cleanup."
    ),
    (
        "User Ollama models",
        HOME / ".ollama/models",
        "Review model names and shared blobs before removal."
    ),
    (
        "Hugging Face models",
        HOME / ".cache/huggingface",
        "Review downloaded models before removal."
    ),
]

review_rows = []

for name, path, note in review_paths:
    size = du(path)

    if size >= 500 * 1024 * 1024:
        review_rows.append((size, name, path, note))

review_rows.sort(reverse=True)

if review_rows:
    for size, name, path, note in review_rows:
        print(f"  {human(size):>10}  REVIEW  {name}")
        print(f"              {path}")
        print(f"              {note}")
        print()
else:
    print("  No large review-only areas detected.")
    print()

print("EXCLUDED FROM AUTOMATIC CLEANUP")
print("  Ollama models")
print("  Hugging Face models")
print("  LyricVid generated videos")
print("  Docker volumes")
print("  Verified duplicates")
print("  Project directories")
print()
print("Those require separate review before removal.")
print()
print("No files were modified.")

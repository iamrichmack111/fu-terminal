#!/usr/bin/env python3
import json
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
    try:
        p = subprocess.run(
            ["du", "-sx", "-B1", str(path)],
            text=True,
            capture_output=True,
            timeout=8
        )
        if p.returncode in (0,1) and p.stdout:
            return int(p.stdout.split("\t",1)[0])
    except Exception:
        pass
    return 0

rows = []

def add(category, label, path, confidence, note):
    path = Path(path)
    if not path.exists():
        return
    size = du(path)
    if size:
        rows.append({
            "category": category,
            "label": label,
            "path": str(path),
            "size": size,
            "confidence": confidence,
            "note": note
        })

# Cache categories
add(
    "CACHE",
    "pip download cache",
    HOME / ".cache/pip",
    "HIGH",
    "Package-download cache; packages can normally be downloaded again."
)

add(
    "CACHE",
    "Playwright browser cache",
    HOME / ".cache/ms-playwright",
    "MEDIUM",
    "Downloaded browser runtimes; removing them may require Playwright to reinstall browsers."
)

add(
    "CACHE",
    "Chrome cache",
    HOME / ".cache/google-chrome",
    "HIGH",
    "Browser cache; Chrome will rebuild it."
)

# Models
add(
    "MODEL",
    "Hugging Face models",
    HOME / ".cache/huggingface",
    "REVIEW",
    "Contains downloaded AI/model assets. Keep models you still use."
)

add(
    "MODEL",
    "Ollama models",
    HOME / ".ollama/models",
    "REVIEW",
    "Active Ollama model storage. Remove models through Ollama rather than deleting blobs."
)

# Generated application output
add(
    "GENERATED OUTPUT",
    "LyricVid jobs",
    HOME / ".local/share/lyricvid/studio-jobs",
    "REVIEW",
    "Rendered job outputs. Verify finished videos exist elsewhere before removing jobs."
)

# Duplicate cache
dup_cache = HOME / "Desktop/FU-Workspace/sessions/duplicate-results.json"

if dup_cache.exists():
    try:
        data = json.loads(dup_cache.read_text())
        reclaim = sum(
            int(g.get("reclaimable",0))
            for g in data.get("groups",[])
        )
        if reclaim:
            rows.append({
                "category": "DUPLICATE",
                "label": "Verified duplicate files",
                "path": "FU duplicate scan",
                "size": reclaim,
                "confidence": "REVIEW",
                "note": "Potential reclaim only. Review FU's duplicate cleanup plan first."
            })
    except Exception:
        pass

rows.sort(key=lambda x: x["size"], reverse=True)

usage = shutil.disk_usage("/")

print()
print("◆ FU STORAGE OPPORTUNITIES")
print("─" * 88)
print("READ ONLY — this report does not delete anything.")
print()
print(
    f"ROOT: {human(usage.used)} used / {human(usage.total)} "
    f"({usage.used / usage.total * 100:.1f}%)"
)
print()

for row in rows:
    print(
        f"{human(row['size']):>10}  "
        f"{row['category']:<18} "
        f"{row['confidence']:<7} "
        f"{row['label']}"
    )
    print(f"            {row['path']}")
    print(f"            {row['note']}")
    print()

high = sum(
    r["size"]
    for r in rows
    if r["confidence"] == "HIGH"
)

review = sum(
    r["size"]
    for r in rows
    if r["confidence"] in ("MEDIUM","REVIEW")
)

print("─" * 88)
print("SUMMARY")
print(f"  High-confidence cache candidates   {human(high)}")
print(f"  Additional review candidates       {human(review)}")
print()

print("RECOMMENDED ORDER")
print("  1. Review high-confidence caches.")
print("  2. Map Ollama storage to model names.")
print("  3. Review Hugging Face models.")
print("  4. Review generated LyricVid jobs.")
print("  5. Review verified duplicate plan.")
print()
print("No files were modified.")

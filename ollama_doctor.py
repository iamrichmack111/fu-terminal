#!/usr/bin/env python3

import os
import shutil
import subprocess
from pathlib import Path

HOME = Path.home()

GIB = 1024 ** 3

# Known/default Ollama storage locations.
CANDIDATE_STORES = [
    ("User", HOME / ".ollama/models"),
    ("System", Path("/usr/share/ollama/.ollama/models")),
]

# Respect an explicitly configured model directory too.
if os.environ.get("OLLAMA_MODELS"):
    CANDIDATE_STORES.insert(
        0,
        ("Configured", Path(os.environ["OLLAMA_MODELS"]).expanduser())
    )


def run(cmd, timeout=8):
    try:
        return subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout
        )
    except Exception:
        return None


def human(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    n = float(n)

    for unit in units:
        if n < 1024 or unit == units[-1]:
            return f"{n:.1f} {unit}"
        n /= 1024


def du(path):
    if not path.exists():
        return 0

    try:
        p = subprocess.run(
            ["du", "-sx", "-B1", str(path)],
            text=True,
            capture_output=True,
            timeout=15
        )

        if p.returncode == 0 and p.stdout:
            return int(p.stdout.split("\t", 1)[0])

    except Exception:
        pass

    return 0


def blobs(path):
    root = path / "blobs"
    found = []

    if not root.is_dir():
        return found

    try:
        for f in root.iterdir():
            if not f.is_file():
                continue

            try:
                found.append((f.stat().st_size, f.name))
            except OSError:
                pass
    except OSError:
        pass

    return sorted(found, reverse=True)


print()
print("◆ FU OLLAMA DOCTOR")
print("─" * 88)
print("READ ONLY — no models or blobs will be removed.")
print()

if not shutil.which("ollama"):
    raise SystemExit("Ollama is not installed.")

# Deduplicate stores in case OLLAMA_MODELS equals a default path.
stores = []
seen = set()

for label, path in CANDIDATE_STORES:
    try:
        key = str(path.resolve())
    except Exception:
        key = str(path)

    if key in seen:
        continue

    seen.add(key)

    if path.exists():
        stores.append({
            "label": label,
            "path": path,
            "size": du(path),
        })

print("MODEL STORES")
print("─" * 88)

if not stores:
    print("  No known Ollama model stores detected.")
else:
    for store in sorted(stores, key=lambda x: x["size"], reverse=True):
        print(
            f"  {store['label']:<12}"
            f"{human(store['size']):>10}  "
            f"{store['path']}"
        )

print()

total_physical = sum(x["size"] for x in stores)

print(f"  Combined physical storage   {human(total_physical)}")
print("  Note: stores are separate; model names may overlap.")
print()

# ------------------------------------------------------------
# Active Ollama API/model inventory
# ------------------------------------------------------------

print("ACTIVE OLLAMA MODEL INVENTORY")
print("─" * 88)

p = run(["ollama", "list"])
models = []

if p and p.returncode == 0:
    lines = p.stdout.splitlines()

    if len(lines) <= 1:
        print("  No models reported by the active Ollama instance.")
    else:
        for line in lines[1:]:
            parts = line.split()

            if not parts:
                continue

            name = parts[0]
            models.append(name)

            # Preserve Ollama's own displayed size rather than attempting
            # to attribute shared blobs to individual models.
            display_size = "unknown"

            if len(parts) >= 4:
                display_size = f"{parts[2]} {parts[3]}"

            print(f"  {name:<50} {display_size}")
else:
    print("  Unable to query the active Ollama instance.")

print()

# ------------------------------------------------------------
# Loaded models
# ------------------------------------------------------------

print("CURRENTLY LOADED")
print("─" * 88)

p = run(["ollama", "ps"])

if p and p.returncode == 0 and p.stdout.strip():
    print(p.stdout)
else:
    print("  No model currently loaded.")

print()

# ------------------------------------------------------------
# FU dependencies
# ------------------------------------------------------------

print("FU DEPENDENCY CHECK")
print("─" * 88)

important = {
    "gemma2:2b": "FU fallback model",
    "embeddinggemma": "possible embedding/RAG model",
    "nomic-embed-text": "possible embedding/RAG model",
}

dependencies = []

for model in models:
    for needle, purpose in important.items():
        if needle in model:
            dependencies.append((model, purpose))

if dependencies:
    for model, purpose in dependencies:
        print(f"  KEEP    {model:<42} {purpose}")
else:
    print("  No known FU model dependency detected in active model list.")

print()

# ------------------------------------------------------------
# Blob inventory PER STORE
# ------------------------------------------------------------

print("BLOB STORAGE")
print("─" * 88)

for store in sorted(stores, key=lambda x: x["size"], reverse=True):
    inventory = blobs(store["path"])

    print()
    print(f"  {store['label']} — {store['path']}")
    print(f"    Blob files       {len(inventory):,}")
    print(f"    Blob bytes       {human(sum(x[0] for x in inventory))}")

    for size, name in inventory[:5]:
        print(f"    {human(size):>10}  {name[:45]}")

print()
print("ASSESSMENT")
print("─" * 88)

if total_physical >= 50 * GIB:
    print(f"  REVIEW — Ollama stores occupy {human(total_physical)} combined.")
elif total_physical >= 10 * GIB:
    print(f"  OBSERVE — Ollama stores occupy {human(total_physical)} combined.")
else:
    print(f"  HEALTHY — Ollama stores occupy {human(total_physical)} combined.")

if len(stores) > 1:
    print(f"  ! Multiple Ollama model stores detected: {len(stores)}.")
    print("    Determine which store the active Ollama service uses before removing models.")

print()
print("SAFE REMOVAL POLICY")
print("─" * 88)
print("  FU will not delete raw Ollama blobs.")
print("  Inspect models with: ollama list")
print("  Remove a selected model with: ollama rm MODEL")
print("  Removal requires explicit approval.")
print()
print("No Ollama data was modified.")

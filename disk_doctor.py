#!/usr/bin/env python3
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HOME = Path.home()
GIB = 1024 ** 3


def human(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    n = float(n)

    for unit in units:
        if n < 1024 or unit == units[-1]:
            return f"{n:.1f} {unit}"
        n /= 1024


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


def root_df():
    """df is authoritative for filesystem pressure."""
    p = run(
        ["df", "-B1", "--output=size,used,avail,pcent", "/"],
        timeout=5
    )

    if not p or p.returncode != 0:
        return None

    try:
        line = p.stdout.strip().splitlines()[-1].split()

        return {
            "total": int(line[0]),
            "used": int(line[1]),
            "avail": int(line[2]),
            "pct": float(line[3].rstrip("%")),
        }
    except Exception:
        return None


def du_bytes(path, timeout=12, sudo=False):
    path = Path(path)

    if not path.exists():
        return 0

    cmd = []

    if sudo:
        cmd += ["sudo", "-n"]

    cmd += ["du", "-sx", "-B1", str(path)]

    p = run(cmd, timeout=timeout)

    if not p or not p.stdout:
        return 0

    try:
        return int(p.stdout.split("\t", 1)[0])
    except Exception:
        return 0


def scan_paths(paths, workers=8, timeout=12, sudo=False):
    def measure(path):
        return du_bytes(path, timeout=timeout, sudo=sudo), Path(path)

    rows = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(measure, path): path
            for path in paths
        }

        for future in as_completed(futures):
            try:
                size, path = future.result()

                if size:
                    rows.append((size, path))
            except Exception:
                pass

    return sorted(rows, key=lambda x: x[0], reverse=True)


def section(title):
    print()
    print(title)
    print("─" * 88)


print()
print("◆ FU DISK DOCTOR")
print("─" * 88)
print("READ ONLY — no files, containers, caches, packages, models, or logs will be removed.")

# -------------------------------------------------------------------
# Authoritative filesystem state
# -------------------------------------------------------------------

df = root_df()

section("FILESYSTEM")

if df:
    print(f"  Root usage          {df['pct']:.1f}%")
    print(f"  Total               {human(df['total'])}")
    print(f"  Used                {human(df['used'])}")
    print(f"  Available           {human(df['avail'])}")
else:
    usage = shutil.disk_usage("/")
    fallback_pct = usage.used / usage.total * 100

    df = {
        "total": usage.total,
        "used": usage.used,
        "avail": usage.free,
        "pct": fallback_pct,
    }

    print(f"  Root usage          {df['pct']:.1f}%  [fallback]")
    print(f"  Total               {human(df['total'])}")
    print(f"  Used                {human(df['used'])}")
    print(f"  Available           {human(df['avail'])}")

# -------------------------------------------------------------------
# Kubernetes
# -------------------------------------------------------------------

section("KUBERNETES")

k8s_disk_pressure = False
k8s_seen = False

if shutil.which("kubectl"):
    p = run([
        "kubectl", "get", "nodes",
        "-o",
        "jsonpath={range .items[*]}{.metadata.name}{\"\\t\"}"
        "{range .status.conditions[?(@.type==\"DiskPressure\")]}"
        "{.status}{\"\\n\"}{end}{end}"
    ], timeout=4)

    if p and p.returncode == 0:
        for line in p.stdout.splitlines():
            if "\t" not in line:
                continue

            k8s_seen = True
            node, status = line.split("\t", 1)
            status = status.strip()

            if status == "True":
                k8s_disk_pressure = True
                print(f"  ✗ {node}: DiskPressure=True")
            else:
                print(f"  ✓ {node}: DiskPressure=False")

if not k8s_seen:
    print("  Kubernetes node conditions unavailable.")

# -------------------------------------------------------------------
# ROOT-FIRST discovery
# -------------------------------------------------------------------

section("ROOT BREAKDOWN")

root_candidates = [
    Path("/var"),
    Path("/usr"),
    Path("/home"),
    Path("/tmp"),
    Path("/opt"),
    Path("/root"),
    Path("/boot"),
]

root_rows = scan_paths(
    root_candidates,
    workers=7,
    timeout=20,
    sudo=True
)

if root_rows:
    for size, path in root_rows:
        print(f"  {human(size):>10}  {path}")
else:
    print("  Root directory sizes unavailable.")
    print("  FU may need passwordless read access for du or a longer scan.")

# -------------------------------------------------------------------
# Targeted root drill-down
# -------------------------------------------------------------------

section("ROOT DRILL-DOWN")

drill_targets = [
    ("/var", [
        "/var/snap",
        "/var/lib",
        "/var/log",
        "/var/tmp",
        "/var/cache",
    ]),
    ("/usr", [
        "/usr/share",
        "/usr/lib",
        "/usr/local",
    ]),
    ("/home", [
        str(HOME),
    ]),
    ("/tmp", []),
]

drill_results = {}

for parent, children in drill_targets:
    parent_size = next(
        (size for size, path in root_rows if str(path) == parent),
        0
    )

    # Don't waste time drilling tiny areas.
    if parent_size < GIB:
        continue

    if parent == "/tmp":
        try:
            children = [
                str(p)
                for p in Path("/tmp").iterdir()
                if not p.is_symlink()
            ]
        except Exception:
            children = []

    if not children:
        continue

    rows = scan_paths(
        children,
        workers=min(6, max(1, len(children))),
        timeout=15,
        sudo=True
    )

    drill_results[parent] = rows

    print()
    print(f"  {parent}")

    for size, path in rows[:8]:
        print(f"    {human(size):>10}  {path}")

# -------------------------------------------------------------------
# Known high-value storage areas
# -------------------------------------------------------------------

section("KNOWN STORAGE AREAS")

known = [
    (
        "/var/snap/docker/common/var-lib-docker",
        "REVIEW",
        "Snap Docker data. Verify whether the Snap Docker daemon is active before any cleanup."
    ),
    (
        "/var/lib/docker",
        "REVIEW",
        "Docker daemon data. Use Docker-native cleanup tools rather than deleting this directory."
    ),
    (
        "/usr/share/ollama/.ollama/models",
        "REVIEW",
        "System-service Ollama model store. Map models with Ollama before removal."
    ),
    (
        str(HOME / ".ollama/models"),
        "REVIEW",
        "User Ollama model store. Map models with Ollama before removal."
    ),
    (
        str(HOME / ".cache/huggingface"),
        "REVIEW",
        "Hugging Face model/cache storage."
    ),
]

known_rows = []

for path, confidence, note in known:
    size = du_bytes(
        path,
        timeout=15,
        sudo=path.startswith(("/var/", "/usr/"))
    )

    if size:
        known_rows.append((size, path, confidence, note))

known_rows.sort(reverse=True)

if known_rows:
    for size, path, confidence, note in known_rows:
        print(f"  {human(size):>10}  {confidence:<7} {path}")
        print(f"              {note}")
else:
    print("  No known large storage areas detected.")

# -------------------------------------------------------------------
# Anomaly detection
# -------------------------------------------------------------------

section("ANOMALIES")

anomalies = []

tmp_size = next(
    (size for size, path in root_rows if str(path) == "/tmp"),
    0
)

if tmp_size >= 10 * GIB:
    anomalies.append(
        (
            "warning",
            f"/tmp is unusually large at {human(tmp_size)}."
        )
    )

tmp_rows = drill_results.get("/tmp", [])

for size, path in tmp_rows:
    if size >= 5 * GIB:
        anomalies.append(
            (
                "warning",
                f"Large temporary tree: {path} ({human(size)}). Review ownership and active processes."
            )
        )

snap_docker = next(
    (
        row for row in known_rows
        if row[1] == "/var/snap/docker/common/var-lib-docker"
    ),
    None
)

if snap_docker and snap_docker[0] >= 10 * GIB:
    anomalies.append(
        (
            "review",
            f"Snap Docker data uses {human(snap_docker[0])}; verify whether this store is active or stale."
        )
    )

system_ollama = next(
    (
        row for row in known_rows
        if row[1] == "/usr/share/ollama/.ollama/models"
    ),
    None
)

if system_ollama and system_ollama[0] >= 10 * GIB:
    anomalies.append(
        (
            "review",
            f"System Ollama model store uses {human(system_ollama[0])}; model-level review only."
        )
    )

if anomalies:
    for level, message in anomalies:
        icon = "!" if level == "warning" else "·"
        print(f"  {icon} {message}")
else:
    print("  ✓ No obvious large temporary-tree anomaly detected.")

# -------------------------------------------------------------------
# Duplicate cache
# -------------------------------------------------------------------

section("DUPLICATES")

duplicate_reclaim = 0
duplicate_groups = 0

cache = (
    HOME
    / "Desktop"
    / "FU-Workspace"
    / "sessions"
    / "duplicate-results.json"
)

if cache.exists():
    try:
        data = json.loads(cache.read_text())
        groups = data.get("groups", [])

        duplicate_groups = len(groups)
        duplicate_reclaim = sum(
            int(g.get("reclaimable", 0))
            for g in groups
        )

        print(f"  Verified groups     {duplicate_groups:,}")
        print(f"  Potential reclaim   {human(duplicate_reclaim)}")
    except Exception:
        print("  Duplicate cache unreadable.")
else:
    print("  No duplicate cache available.")

# -------------------------------------------------------------------
# Active Docker daemon
# -------------------------------------------------------------------

section("ACTIVE DOCKER")

if shutil.which("docker"):
    root = run(
        ["docker", "info", "--format", "{{.DockerRootDir}}"],
        timeout=4
    )

    if root and root.returncode == 0:
        print(f"  Docker root         {root.stdout.strip()}")

    p = run(["docker", "system", "df"], timeout=5)

    if p and p.returncode == 0:
        for line in p.stdout.splitlines():
            print(" ", line)
    else:
        print("  Docker disk information unavailable.")
else:
    print("  Docker not installed.")

# -------------------------------------------------------------------
# Journal
# -------------------------------------------------------------------

section("SYSTEM JOURNAL")

journal_bytes = 0

if shutil.which("journalctl"):
    p = run(["journalctl", "--disk-usage"], timeout=4)

    if p:
        text = (p.stdout + p.stderr).strip()
        print(" ", text or "Unable to determine journal size.")

        m = re.search(
            r"take up\s+([\d.]+)([KMGT])",
            text,
            re.I
        )

        if m:
            value = float(m.group(1))
            unit = m.group(2).upper()

            journal_bytes = int(value * {
                "K": 1024,
                "M": 1024 ** 2,
                "G": 1024 ** 3,
                "T": 1024 ** 4,
            }[unit])
else:
    print("  journalctl unavailable.")

# -------------------------------------------------------------------
# Final assessment
# -------------------------------------------------------------------

section("ASSESSMENT")

pct = df["pct"]

if pct >= 95:
    print(f"  ✗ Root filesystem critically full: {pct:.1f}%")
elif pct >= 90:
    print(f"  ✗ Root filesystem under heavy pressure: {pct:.1f}%")
elif pct >= 80:
    print(f"  ! Root filesystem elevated: {pct:.1f}%")
else:
    print(f"  ✓ Root filesystem capacity acceptable: {pct:.1f}%")

if k8s_disk_pressure:
    print("  ✗ Kubernetes currently reports DiskPressure")
else:
    print("  ✓ No current Kubernetes DiskPressure detected")

if root_rows:
    size, path = root_rows[0]
    print(f"  · Largest root area: {path} ({human(size)})")

for level, message in anomalies:
    icon = "!" if level == "warning" else "·"
    print(f"  {icon} {message}")

if duplicate_reclaim:
    print(
        f"  · Verified duplicate opportunity: "
        f"{human(duplicate_reclaim)}"
    )

print()

if pct >= 90 or k8s_disk_pressure:
    print("STATUS: ATTENTION REQUIRED")
elif pct >= 80:
    print("STATUS: WATCH")
else:
    print("STATUS: HEALTHY")

print()
print("SAFE NEXT STEP")
print('  fu --auto "storage opportunities"')
print()
print("No files were modified.")

#!/usr/bin/env python3

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WS = Path.home() / "Desktop" / "FU-Workspace"
STATE = WS / "sessions" / "investigation-last.json"


def run(args, timeout=12):
    try:
        p = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout
        )
        return p.returncode, p.stdout.strip()
    except Exception:
        return 1, ""


def disk():
    evidence = []

    # --------------------------------------------------------
    # Filesystem capacity
    # --------------------------------------------------------

    rc, raw = run(["df", "-P", "-B1", "/"])

    if rc == 0 and len(raw.splitlines()) >= 2:
        parts = raw.splitlines()[-1].split()

        try:
            used = int(parts[2])
            avail = int(parts[3])
            pct = float(parts[4].rstrip("%"))

            evidence.append({
                "signal": "root filesystem usage",
                "value": f"{pct:.1f}%",
                "status": (
                    "critical" if pct >= 90
                    else "warning" if pct >= 85
                    else "ok"
                ),
                "authority": "current",
                "source": "df",
            })

            evidence.append({
                "signal": "root available bytes",
                "value": avail,
                "status": "ok" if avail > 0 else "critical",
                "authority": "current",
                "source": "df",
            })

        except Exception:
            pass

    # --------------------------------------------------------
    # Inodes
    # --------------------------------------------------------

    rc, raw = run(["df", "-Pi", "/"])

    if rc == 0 and len(raw.splitlines()) >= 2:
        parts = raw.splitlines()[-1].split()

        try:
            pct = float(parts[4].rstrip("%"))

            evidence.append({
                "signal": "root inode usage",
                "value": f"{pct:.1f}%",
                "status": (
                    "critical" if pct >= 95
                    else "warning" if pct >= 85
                    else "ok"
                ),
                "authority": "current",
                "source": "df -i",
            })

        except Exception:
            pass

    # --------------------------------------------------------
    # Deleted but still-open files
    #
    # File count alone is NOT a storage-health signal.
    # Measure bytes pinned by deleted regular files instead.
    #
    # /proc is authoritative for the running processes and
    # avoids treating lsof warning text or duplicate FDs as
    # reclaimed-space estimates.
    # --------------------------------------------------------

    deleted_count = 0
    deleted_bytes = 0
    seen_deleted = set()

    # Only count deleted files residing on the root filesystem.
    # memfd/tmpfs/shm objects consume memory-backed storage and must
    # not be reported as reclaimable capacity on /.
    try:
        root_device = Path("/").stat().st_dev
    except OSError:
        root_device = None

    proc = Path("/proc")

    if proc.exists():
        for pid_dir in proc.iterdir():
            if not pid_dir.name.isdigit():
                continue

            fd_dir = pid_dir / "fd"

            try:
                fds = list(fd_dir.iterdir())
            except (PermissionError, FileNotFoundError, ProcessLookupError):
                continue

            for fd in fds:
                try:
                    target = fd.readlink()
                    target_text = str(target)

                    if " (deleted)" not in target_text:
                        continue

                    st = fd.stat()

                    # Ignore memfd, tmpfs, shm and files belonging to
                    # other mounts. This investigation is specifically
                    # measuring reclaimable capacity on /.
                    if root_device is None or st.st_dev != root_device:
                        continue

                    # Same inode may be referenced by several FDs.
                    key = (st.st_dev, st.st_ino)

                    if key in seen_deleted:
                        continue

                    seen_deleted.add(key)
                    deleted_count += 1

                    if st.st_size > 0:
                        deleted_bytes += st.st_size

                except (
                    PermissionError,
                    FileNotFoundError,
                    ProcessLookupError,
                    OSError,
                ):
                    continue

    # Severity is based on pinned capacity, not object count.
    #
    # <100 MiB   informational / healthy
    # 100 MiB-1G warning
    # >=1 GiB    critical storage signal
    if deleted_bytes >= 1024 ** 3:
        deleted_status = "critical"
    elif deleted_bytes >= 100 * 1024 ** 2:
        deleted_status = "warning"
    else:
        deleted_status = "ok"

    evidence.append({
        "signal": "rootfs deleted open files",
        "value": deleted_count,
        "status": "ok",
        "authority": "current",
        "source": "/proc/*/fd",
    })

    evidence.append({
        "signal": "rootfs deleted open bytes",
        "value": deleted_bytes,
        "status": deleted_status,
        "authority": "current",
        "source": "/proc/*/fd",
        "format": "bytes",
    })

    # --------------------------------------------------------
    # Kubernetes DiskPressure
    # --------------------------------------------------------

    if shutil.which("kubectl"):
        rc, raw = run(["kubectl", "get", "nodes", "-o", "json"])

        if rc == 0:
            try:
                nodes = json.loads(raw).get("items", [])

                for node in nodes:
                    name = node.get("metadata", {}).get("name", "unknown")

                    conditions = {
                        c.get("type"): c.get("status")
                        for c in node.get("status", {}).get("conditions", [])
                    }

                    pressure = conditions.get("DiskPressure")

                    evidence.append({
                        "signal": f"kubernetes {name} DiskPressure",
                        "value": pressure,
                        "status": (
                            "critical" if pressure == "True"
                            else "ok"
                        ),
                        "authority": "current",
                        "source": "kubectl",
                    })

            except Exception:
                pass

    return evidence


def confidence(evidence):
    current = [
        e for e in evidence
        if e.get("authority") == "current"
    ]

    sources = {
        e.get("source")
        for e in current
        if e.get("source")
    }

    if len(current) >= 3 and len(sources) >= 2:
        return "HIGH"

    if current:
        return "MEDIUM"

    return "LOW"


def investigate_disk():
    evidence = disk()

    critical = [
        e for e in evidence
        if e["status"] == "critical"
    ]

    warnings = [
        e for e in evidence
        if e["status"] == "warning"
    ]

    if critical:
        status = "ATTENTION REQUIRED"
    elif warnings:
        status = "WATCH"
    elif evidence:
        status = "HEALTHY"
    else:
        status = "UNKNOWN"

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": "disk",
        "status": status,
        "confidence": confidence(evidence),
        "evidence": evidence,
    }

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(result, indent=2))

    print()
    print("◆ FU INVESTIGATE — DISK")
    print("─" * 88)
    print("READ ONLY — FU will not remove or modify anything.")
    print()

    print("OBSERVE")
    print("─" * 88)

    symbols = {
        "ok": "✓",
        "warning": "!",
        "critical": "✗",
    }

    if evidence:
        for e in evidence:
            value = e["value"]

            if e.get("format") == "bytes":
                n = float(value)
                units = ["B", "KB", "MB", "GB", "TB"]
                unit = "B"

                for unit in units:
                    if n < 1024 or unit == units[-1]:
                        break
                    n /= 1024

                value = f"{n:.1f} {unit}"

            elif isinstance(value, int):
                value = f"{value:,}"

            print(
                f"  {symbols[e['status']]} "
                f"{e['signal']:<44} "
                f"{str(value):>12}  "
                f"[{e['source']}]"
            )
    else:
        print("  No usable observations collected.")

    print()
    print("DIAGNOSIS")
    print("─" * 88)
    print(f"  STATUS       {status}")
    print(f"  CONFIDENCE   {result['confidence']}")

    print()

    if status == "HEALTHY":
        print("  Current signals do not indicate filesystem pressure.")
        print("  No corrective action is required for filesystem health.")

    elif status == "WATCH":
        print("  One or more current signals merit observation.")
        print("  Review storage opportunities before removing anything.")

    elif status == "ATTENTION REQUIRED":
        print("  Current authoritative evidence indicates a storage problem.")
        print("  Diagnose the affected signal before making changes.")

    else:
        print("  FU did not collect enough evidence for a diagnosis.")

    print()
    print("NEXT")
    print("─" * 88)

    if status in ("WATCH", "ATTENTION REQUIRED"):
        print('  fu --auto "storage opportunities"')
    else:
        print("  No immediate corrective action indicated.")

    print()
    print("No files, processes, containers, or cluster resources were modified.")


def dispatch(argv):
    if not argv or argv[0].lower() != "investigate":
        return False

    if len(argv) < 2:
        print("Usage: fu investigate disk")
        return True

    scope = argv[1].lower()

    if scope in ("disk", "storage"):
        investigate_disk()
    else:
        print(f"Unknown investigation: {scope}")
        print("Available: disk")

    return True

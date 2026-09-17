#!/usr/bin/env python3

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WS = Path.home() / "Desktop" / "FU-Workspace"
STATE = WS / "sessions" / "evidence-last.json"


def run(args, timeout=8):
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


def root_disk():
    rc, raw = run(["df", "-P", "-B1", "/"])

    if rc != 0:
        return []

    lines = raw.splitlines()

    if len(lines) < 2:
        return []

    parts = lines[-1].split()

    if len(parts) < 6:
        return []

    try:
        size = int(parts[1])
        used = int(parts[2])
        avail = int(parts[3])
        pct = float(parts[4].rstrip("%"))
    except Exception:
        return []

    return [
        {
            "key": "filesystem.root.usage",
            "value": pct,
            "unit": "%",
            "status": (
                "critical" if pct >= 90
                else "warning" if pct >= 85
                else "ok"
            ),
            "authority": "current",
            "source": "df",
        },
        {
            "key": "filesystem.root.available",
            "value": avail,
            "unit": "bytes",
            "status": "ok",
            "authority": "current",
            "source": "df",
        },
    ]


def kubernetes():
    if not shutil.which("kubectl"):
        return []

    rc, raw = run(["kubectl", "get", "nodes", "-o", "json"])

    if rc != 0:
        return []

    try:
        data = json.loads(raw)
    except Exception:
        return []

    evidence = []

    for node in data.get("items", []):
        name = node.get("metadata", {}).get("name", "unknown")

        conditions = {
            x.get("type"): x.get("status")
            for x in node.get("status", {}).get("conditions", [])
        }

        ready = conditions.get("Ready")
        disk = conditions.get("DiskPressure")
        memory = conditions.get("MemoryPressure")
        pid = conditions.get("PIDPressure")

        evidence.append({
            "key": f"kubernetes.node.{name}.ready",
            "value": ready,
            "status": "ok" if ready == "True" else "critical",
            "authority": "current",
            "source": "kubectl",
        })

        evidence.append({
            "key": f"kubernetes.node.{name}.disk_pressure",
            "value": disk,
            "status": "critical" if disk == "True" else "ok",
            "authority": "current",
            "source": "kubectl",
        })

        evidence.append({
            "key": f"kubernetes.node.{name}.memory_pressure",
            "value": memory,
            "status": "critical" if memory == "True" else "ok",
            "authority": "current",
            "source": "kubectl",
        })

        evidence.append({
            "key": f"kubernetes.node.{name}.pid_pressure",
            "value": pid,
            "status": "critical" if pid == "True" else "ok",
            "authority": "current",
            "source": "kubectl",
        })

    return evidence


def collect(scope="all"):
    scope = scope.lower().strip()

    evidence = []

    if scope in ("all", "disk", "storage"):
        evidence.extend(root_disk())

    if scope in ("all", "k8s", "kubernetes"):
        evidence.extend(kubernetes())

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "evidence": evidence,
    }

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(result, indent=2))

    return result


def confidence(evidence):
    current = [
        e for e in evidence
        if e.get("authority") == "current"
    ]

    if len(current) >= 3:
        return "HIGH"

    if current:
        return "MEDIUM"

    return "LOW"


def human_bytes(n):
    try:
        n = float(n)
    except Exception:
        return str(n)

    units = ["B", "KB", "MB", "GB", "TB"]

    for unit in units:
        if n < 1024 or unit == units[-1]:
            return f"{n:.1f} {unit}"
        n /= 1024


def display_value(e):
    value = e.get("value")
    unit = e.get("unit")

    if unit == "bytes":
        return human_bytes(value)

    if unit == "%":
        return f"{float(value):.1f}%"

    return str(value)


def print_report(result):
    evidence = result["evidence"]

    print()
    print("◆ FU EVIDENCE")
    print("─" * 88)
    print(f"  Scope        {result['scope']}")
    print(f"  Confidence   {confidence(evidence)}")
    print()

    if not evidence:
        print("  No authoritative evidence available for this scope.")
        print()
        print("No commands were modified and no corrective action was taken.")
        return

    print("EVIDENCE")
    print("─" * 88)

    symbols = {
        "ok": "✓",
        "warning": "!",
        "critical": "✗",
        "observation": "○",
    }

    for e in evidence:
        symbol = symbols.get(e.get("status"), "○")

        print(
            f"  {symbol} "
            f"{e['key']:<48} "
            f"{display_value(e):>12}  "
            f"[{e.get('source', 'unknown')}]"
        )

    critical = [e for e in evidence if e.get("status") == "critical"]
    warning = [e for e in evidence if e.get("status") == "warning"]

    print()
    print("ASSESSMENT")
    print("─" * 88)

    if critical:
        print("  STATUS       ATTENTION REQUIRED")
    elif warning:
        print("  STATUS       WATCH")
    else:
        print("  STATUS       HEALTHY")

    print(f"  CONFIDENCE   {confidence(evidence)}")
    print()
    print("Evidence collection is read-only.")


def dispatch(argv):
    if not argv or argv[0].lower() != "evidence":
        return False

    scope = argv[1] if len(argv) > 1 else "all"

    if scope.lower() not in (
        "all",
        "disk",
        "storage",
        "k8s",
        "kubernetes",
    ):
        print(f"Unknown evidence scope: {scope}")
        print("Available: all, disk, storage, kubernetes")
        return True

    print_report(collect(scope))
    return True

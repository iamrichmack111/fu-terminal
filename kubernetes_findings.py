#!/usr/bin/env python3
import subprocess
import json
from datetime import datetime, timezone, timedelta

NOW = datetime.now(timezone.utc)
RECENT = NOW - timedelta(hours=1)
DAY = NOW - timedelta(hours=24)

def run(args):
    try:
        p = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=8
        )
        return p.returncode, p.stdout.strip()
    except Exception:
        return 1, ""

def event_time(e):
    candidates = [
        e.get("eventTime"),
        e.get("series", {}).get("lastObservedTime"),
        e.get("lastTimestamp"),
        e.get("firstTimestamp"),
        e.get("metadata", {}).get("creationTimestamp"),
    ]

    for value in candidates:
        if not value:
            continue
        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except Exception:
            pass

    return None

current = []
recent = []
history = []

# Current node conditions are authoritative for deciding whether
# historical storage events represent an active incident.
current_disk_pressure = False

# ----------------------------------------------------------
# Current nodes
# ----------------------------------------------------------

rc, raw = run(["kubectl", "get", "nodes", "-o", "json"])

if rc == 0:
    nodes = json.loads(raw).get("items", [])
    ready = 0

    for node in nodes:
        name = node["metadata"]["name"]

        conditions = {
            c["type"]: c["status"]
            for c in node.get("status", {}).get("conditions", [])
        }

        if conditions.get("Ready") == "True":
            ready += 1
        else:
            current.append(("critical", f"Node {name} is NOT Ready"))

        for condition in ("DiskPressure", "MemoryPressure", "PIDPressure"):
            if conditions.get(condition) == "True":
                current.append(
                    ("critical", f"Node {name} currently reports {condition}")
                )

                if condition == "DiskPressure":
                    current_disk_pressure = True

    current.insert(
        0,
        ("ok", f"{ready}/{len(nodes)} nodes currently Ready")
    )

# ----------------------------------------------------------
# Current pods
# ----------------------------------------------------------

rc, raw = run(["kubectl", "get", "pods", "-A", "-o", "json"])

if rc == 0:
    pods = json.loads(raw).get("items", [])
    healthy = 0

    for pod in pods:
        ns = pod["metadata"]["namespace"]
        name = pod["metadata"]["name"]
        status = pod.get("status", {})
        phase = status.get("phase", "Unknown")
        containers = status.get("containerStatuses", [])

        fully_ready = (
            all(c.get("ready", False) for c in containers)
            if containers
            else phase == "Succeeded"
        )

        if phase in ("Running", "Succeeded") and fully_ready:
            healthy += 1
        else:
            current.append(
                ("critical", f"Pod {ns}/{name} is {phase} and not fully ready")
            )

        restarts = sum(
            c.get("restartCount", 0)
            for c in containers
        )

        if restarts >= 10:
            history.append(
                f"{ns}/{name}: {restarts} historical container restarts"
            )

    current.insert(
        1,
        ("ok", f"{healthy}/{len(pods)} pods currently healthy")
    )

# ----------------------------------------------------------
# Events by age
# ----------------------------------------------------------

rc, raw = run([
    "kubectl", "get", "events", "-A",
    "--field-selector", "type=Warning",
    "-o", "json"
])

if rc == 0:
    events = json.loads(raw).get("items", [])

    recent_reasons = {}
    day_reasons = {}
    old_reasons = {}

    for event in events:
        reason = event.get("reason", "Unknown")
        when = event_time(event)

        if when and when >= RECENT:
            bucket = recent_reasons
        elif when and when >= DAY:
            bucket = day_reasons
        else:
            bucket = old_reasons

        bucket[reason] = bucket.get(reason, 0) + 1

    disk_recent = sum(
        recent_reasons.get(x, 0)
        for x in ("FreeDiskSpaceFailed", "ImageGCFailed")
    )

    if disk_recent:
        recent.append(
            ("critical",
             f"{disk_recent} disk-space/image-GC warning event(s) within the last hour")
        )

    oom_recent = recent_reasons.get("SystemOOM", 0)
    if oom_recent:
        recent.append(
            ("critical", f"{oom_recent} SystemOOM event(s) within the last hour")
        )

    disk_day = sum(
        day_reasons.get(x, 0)
        for x in ("FreeDiskSpaceFailed", "ImageGCFailed")
    )

    if disk_day:
        recent.append(
            ("warning",
             f"{disk_day} additional disk-space/image-GC warning event(s) within 24 hours")
        )

    old_disk = sum(
        old_reasons.get(x, 0)
        for x in ("FreeDiskSpaceFailed", "ImageGCFailed")
    )

    if old_disk:
        history.append(
            f"{old_disk} older disk-space/image-GC event(s)"
        )

    old_oom = (
        day_reasons.get("SystemOOM", 0)
        + old_reasons.get("SystemOOM", 0)
    )

    if old_oom:
        history.append(
            f"{old_oom} older SystemOOM event(s)"
        )

    old_nr = (
        day_reasons.get("NodeNotReady", 0)
        + old_reasons.get("NodeNotReady", 0)
    )

    if old_nr:
        history.append(
            f"{old_nr} historical NodeNotReady event(s)"
        )

# ----------------------------------------------------------
# Output
# ----------------------------------------------------------

print("◆ FU KUBERNETES FINDINGS")
print("─" * 76)

print()
print("CURRENT STATE")

for level, msg in current:
    symbol = {
        "ok": "✓",
        "warning": "!",
        "critical": "✗"
    }[level]

    print(symbol, msg)

print()
print("RECENT EVENTS")

if recent:
    for level, msg in recent:
        print("✗" if level == "critical" else "!", msg)
else:
    print("✓ No significant warning events detected within the last hour")

print()
print("HISTORY")

if history:
    for msg in history:
        print("·", msg)
else:
    print("· No notable historical observations")

current_critical = any(
    level == "critical"
    for level, _ in current
)

recent_critical = any(
    level == "critical"
    for level, _ in recent
)

recent_warning = any(
    level == "warning"
    for level, _ in recent
)

print()
print("─" * 76)

# Historical disk warnings do not override a recovered current node.
# Current conditions win.
if current_critical:
    print("STATUS: ATTENTION REQUIRED")
elif recent_critical and current_disk_pressure:
    print("STATUS: ATTENTION REQUIRED")
elif recent_critical or recent_warning or history:
    print("STATUS: HEALTHY WITH OBSERVATIONS")
else:
    print("STATUS: HEALTHY")

print()

disk_problem = any(
    "disk" in msg.lower()
    for level, msg in current + recent
    if level in ("critical", "warning")
)

if disk_problem and current_disk_pressure:
    print('NEXT: fu --auto "disk doctor"')
elif current_critical:
    print("NEXT: inspect the affected node or pod.")
elif disk_problem:
    print("NEXT: no immediate corrective action indicated; disk warnings are historical.")
else:
    print("NEXT: no immediate corrective action indicated.")

print()
print("Analysis is read-only. No cluster resources were modified.")

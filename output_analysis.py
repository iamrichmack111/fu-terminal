#!/usr/bin/env python3
import re


def _age_to_minutes(age):
    """Best-effort Kubernetes AGE parser: 30s, 10m, 2h, 3d, 5d5h."""
    if not age:
        return None

    total = 0.0
    found = False

    units = {
        "d": 1440,
        "h": 60,
        "m": 1,
        "s": 1 / 60,
    }

    for value, unit in re.findall(r"(\d+)([dhms])", age.lower()):
        total += int(value) * units[unit]
        found = True

    return total if found else None


def analyze_kubernetes(text):
    findings = []

    # ------------------------------------------------------
    # Current pod state
    # ------------------------------------------------------
    total = 0
    unhealthy = []

    for line in text.splitlines():
        parts = line.split()

        if len(parts) < 4:
            continue

        if parts[0] not in ("default", "kube-system"):
            continue

        status = parts[3]

        valid_states = {
            "Running", "Pending", "Failed", "Unknown",
            "CrashLoopBackOff", "Error", "Completed"
        }

        if status not in valid_states:
            continue

        total += 1

        if status not in ("Running", "Completed"):
            unhealthy.append((parts[1], status))

    if total:
        if unhealthy:
            findings.append(
                ("bad", f"{len(unhealthy)}/{total} pods are unhealthy.")
            )
            for name, status in unhealthy[:5]:
                findings.append(("bad", f"{name}: {status}"))
        else:
            findings.append(
                ("ok", f"All {total} listed pods are currently running.")
            )

    # ------------------------------------------------------
    # CURRENT DiskPressure state
    #
    # Current node condition is authoritative.
    # Do NOT let old events override DiskPressure=False.
    # ------------------------------------------------------
    disk_pressure_true = bool(re.search(
        r"(?:DiskPressure|DISK_PRESSURE|DISK)\s*[=:]?\s*True\b",
        text,
        re.I
    ))

    disk_pressure_false = bool(re.search(
        r"(?:DiskPressure|DISK_PRESSURE|DISK)\s*[=:]?\s*False\b",
        text,
        re.I
    ))

    no_disk_pressure_event = "NodeHasNoDiskPressure" in text

    if disk_pressure_false or no_disk_pressure_event:
        findings.append((
            "ok",
            "The node currently reports no DiskPressure."
        ))
    elif disk_pressure_true:
        findings.append((
            "bad",
            "The node currently reports DiskPressure=True."
        ))

    # ------------------------------------------------------
    # Historical/recent storage events
    # ------------------------------------------------------
    disk_lines = [
        line for line in text.splitlines()
        if re.search(r"FreeDiskSpaceFailed|ImageGCFailed", line, re.I)
    ]

    eviction_lines = [
        line for line in text.splitlines()
        if re.search(r"EvictionThresholdMet", line, re.I)
    ]

    active_disk_events = []
    historical_disk_events = []

    for line in disk_lines:
        parts = line.split()
        age = parts[1] if len(parts) > 1 else ""
        mins = _age_to_minutes(age)

        # Treat <=5m as potentially active evidence.
        if mins is not None and mins <= 5:
            active_disk_events.append(line)
        else:
            historical_disk_events.append(line)

    active_evictions = []
    historical_evictions = []

    for line in eviction_lines:
        parts = line.split()
        age = parts[1] if len(parts) > 1 else ""
        mins = _age_to_minutes(age)

        if mins is not None and mins <= 5:
            active_evictions.append(line)
        else:
            historical_evictions.append(line)

    if active_disk_events:
        findings.append((
            "bad",
            f"{len(active_disk_events)} current/recent disk-space warning "
            f"event(s) are displayed."
        ))

    if active_evictions:
        findings.append((
            "bad",
            "Kubernetes recently attempted ephemeral-storage reclamation."
        ))

    historical_count = (
        len(historical_disk_events)
        + len(historical_evictions)
    )

    if historical_count:
        findings.append((
            "warn",
            f"{historical_count} older storage-pressure event(s) are shown "
            f"for historical context."
        ))

    if disk_lines:
        line = disk_lines[-1]
        parts = line.split()
        age = parts[1] if len(parts) > 1 else "unknown"

        m = re.search(r"\((\d+)% of .*? used\)", line)
        pct = m.group(1) if m else None

        if pct:
            findings.append((
                "warn",
                f"Latest displayed historical disk warning is {age} old "
                f"and reported {pct}% usage."
            ))

    # ------------------------------------------------------
    # Other historical evidence
    # ------------------------------------------------------
    if "SystemOOM" in text:
        m = re.search(
            r"victim process:\s*([^,\n]+)",
            text,
            re.I
        )

        victim = m.group(1).strip() if m else "a process"

        findings.append((
            "warn",
            f"History includes a SystemOOM involving {victim}."
        ))

    if "NodeNotReady" in text:
        findings.append((
            "warn",
            "History includes NodeNotReady events."
        ))

    # ------------------------------------------------------
    # Assessment
    # ------------------------------------------------------
    active_storage_problem = (
        disk_pressure_true
        or bool(active_disk_events)
        or bool(active_evictions)
    )

    recovered_storage = (
        (disk_pressure_false or no_disk_pressure_event)
        and not active_disk_events
        and not active_evictions
    )

    if unhealthy:
        assessment = (
            "One or more workloads are currently unhealthy. "
            "Inspect Kubernetes before making unrelated changes."
        )
        next_cmd = 'fu --auto "kubernetes doctor"'

    elif recovered_storage:
        assessment = (
            "The node currently reports no DiskPressure and no active "
            "storage-reclamation evidence is displayed. Older disk warnings "
            "are historical observations and do not indicate a current "
            "storage emergency."
        )
        next_cmd = None

    elif active_storage_problem:
        assessment = (
            "Current Kubernetes evidence indicates active node storage "
            "pressure. Diagnose filesystem usage before making unrelated "
            "cluster changes."
        )
        next_cmd = 'fu --auto "disk doctor"'

    elif total:
        assessment = (
            "The listed Kubernetes workloads currently appear healthy."
        )
        next_cmd = None

    else:
        return None

    return {
        "title": "FU ANALYSIS",
        "findings": findings,
        "assessment": assessment,
        "next": next_cmd,
    }


def analyze(rule_id, output, returncode=0):
    if returncode != 0:
        return None

    if rule_id in (
        "k8s-pods-events",
        "kubernetes-doctor",
        "k8s-storage-doctor",
    ):
        return analyze_kubernetes(output)

    return None


def print_analysis(result):
    if not result:
        return

    print()
    print("─" * 100)
    print("◆ FU ANALYSIS")
    print("─" * 100)
    print()

    icons = {
        "ok": "✓",
        "warn": "·",
        "bad": "✗",
    }

    for level, message in result.get("findings", []):
        print(f"  {icons.get(level, '·')} {message}")

    print()
    print("  ASSESSMENT")
    print(" ", result["assessment"])

    if result.get("next"):
        print()
        print("  TRY NEXT")
        print(" ", result["next"])

#!/usr/bin/env python3
import re


def human_bytes(text):
    m = re.search(r"Potential saving\s*:\s*([^\n]+)", text, re.I)
    return m.group(1).strip() if m else None


def duplicate_groups(text):
    m = re.search(r"Duplicate groups\s*:\s*([\d,]+)", text, re.I)
    return m.group(1) if m else None


def disk_percent(text):
    """
    Understand both traditional df output and FU Doctor output.
    """
    vals = []

    for line in text.splitlines():

        # Traditional df output
        m = re.search(r"\s(\d+)%\s+(/\S*|/)$", line)
        if m:
            vals.append((float(m.group(1)), m.group(2)))

        # FU Disk Doctor:
        # Root usage          90.2%
        m = re.search(r"Root usage\s+([\d.]+)%", line, re.I)
        if m:
            vals.append((float(m.group(1)), "/"))

    return max(vals) if vals else None


def has_disk_pressure(output):
    """
    Return True only when output contains evidence of CURRENT DiskPressure.

    Historical Kubernetes events such as NodeHasDiskPressure and
    EvictionThresholdMet do not establish the current condition.
    """

    # Authoritative/current recovery evidence wins.
    healthy = [
        r"DiskPressure\s*(?:=|:)?\s*False",
        r"KubeletHasNoDiskPressure",
        r"NodeHasNoDiskPressure",
        r"currently reports no DiskPressure",
    ]

    if any(re.search(x, output, re.I | re.M) for x in healthy):
        return False

    active = [
        r"DiskPressure\s*(?:=|:)?\s*True",
        r"currently reports DiskPressure",
        r"current(?:ly)?[^\n]{0,80}DiskPressure[^\n]{0,40}True",
    ]

    return any(
        re.search(x, output, re.I | re.M)
        for x in active
    )


def make(title, message, next_cmd=None, next_rule=None):
    return {
        "title": title,
        "message": message,
        "next": next_cmd,
        "_next_rule": next_rule,
    }


def suggest(req, output, returncode=0, current_rule=None):
    """
    Return one deterministic next-step suggestion.

    current_rule is the curated/builtin rule that just executed.
    This prevents FU from suggesting the same route again.
    """

    if returncode != 0:
        return make(
            "COMMAND FAILED",
            "Inspect the failure before trying another operation."
        )

    q = req.lower()

    # ---------------------------------------------------------
    # Explicit workflow transitions by rule ID
    # ---------------------------------------------------------

    if current_rule == "k8s-pods-events":
        # Never suggest k8s-pods-events after k8s-pods-events.
        if has_disk_pressure(output):
            candidate = make(
                "FU SUGGESTION",
                "Recent Kubernetes events include disk-pressure activity. "
                "Use Disk Doctor to check the filesystem's current state.",
                'fu --auto "disk doctor"',
                "disk-doctor",
            )
        else:
            return None

    elif current_rule == "kubernetes-doctor":
        if has_disk_pressure(output):
            candidate = make(
                "FU SUGGESTION",
                "Kubernetes reports disk pressure. Inspect current storage "
                "usage before changing cluster resources.",
                'fu --auto "disk doctor"',
                "disk-doctor",
            )
        else:
            return None

    elif current_rule == "disk-doctor":
        candidate = make(
            "FU SUGGESTION",
            "Disk Doctor has identified the current storage state. "
            "Review reclaim opportunities before deleting anything.",
            'fu --auto "storage opportunities"',
            "storage-opportunities",
        )

    elif current_rule == "storage-opportunities":
        candidate = make(
            "FU SUGGESTION",
            "Storage opportunities are classified. Build a read-only "
            "cleanup plan to estimate the effect before removing anything.",
            'fu --auto "cleanup plan"',
            "cleanup-plan",
        )

    elif current_rule == "cleanup-plan":
        # Plan is the end of the automatic/read-only cleanup chain.
        return None

    elif current_rule == "ollama-doctor":
        return None

    elif current_rule == "analyze-cache-storage":
        candidate = make(
            "FU SUGGESTION",
            "Cache storage has been analyzed. Review all storage "
            "opportunities before deciding what to remove.",
            'fu --auto "storage opportunities"',
            "storage-opportunities",
        )

    elif current_rule in (
        "analyze-ollama-storage",
        "analyze-local-storage",
    ):
        candidate = make(
            "FU SUGGESTION",
            "This storage area has been analyzed. Compare it with the "
            "other reclaim opportunities before removing anything.",
            'fu --auto "storage opportunities"',
            "storage-opportunities",
        )

    # ---------------------------------------------------------
    # Duplicate workflow
    # ---------------------------------------------------------

    elif current_rule == "review-safe-duplicate-files":
        candidate = make(
            "FU SUGGESTION",
            "FU has identified duplicate groups worth reviewing. "
            "The next step is a read-only KEEP/REMOVE plan.",
            'fu --auto "make a duplicate cleanup plan"',
            "duplicate-cleanup-plan",
        )

    elif current_rule == "duplicate-cleanup-plan":
        return None

    elif "safest duplicate" in q or "review duplicate" in q:
        candidate = make(
            "FU SUGGESTION",
            "FU has identified duplicate groups worth reviewing. "
            "The next step is a read-only KEEP/REMOVE plan.",
            'fu --auto "make a duplicate cleanup plan"',
            "duplicate-cleanup-plan",
        )

    elif "duplicate" in q:
        groups = duplicate_groups(output)
        saving = human_bytes(output)

        if groups and saving:
            candidate = make(
                "FU SUGGESTION",
                f"{groups} duplicate groups were found with approximately "
                f"{saving} potentially reclaimable. Review them before "
                "deleting anything.",
                'fu "show me the safest duplicate files I can remove"',
                "review-safe-duplicate-files",
            )
        else:
            return None

    # ---------------------------------------------------------
    # Generic disk/storage
    # ---------------------------------------------------------

    elif "disk" in q or "storage" in q:
        usage = disk_percent(output)

        if usage:
            pct, mount = usage

            if pct >= 90:
                candidate = make(
                    "FU SUGGESTION",
                    f"{mount} is {pct:.1f}% full. Review classified storage "
                    "opportunities before removing anything.",
                    'fu --auto "storage opportunities"',
                    "storage-opportunities",
                )

            elif pct >= 85:
                candidate = make(
                    "FU SUGGESTION",
                    f"{mount} is {pct:.1f}% full. Filesystem usage is "
                    "elevated but not critical. Optional storage review "
                    "may be useful soon.",
                    'fu --auto "storage opportunities"',
                    "storage-opportunities",
                )
            else:
                return None
        else:
            return None

    # ---------------------------------------------------------
    # Memory
    # ---------------------------------------------------------

    elif "memory" in q or "ram" in q:
        candidate = make(
            "FU SUGGESTION",
            "If memory pressure is the concern, inspect the processes "
            "using the most RAM.",
            'fu "show processes using the most memory"',
            "top-memory-processes",
        )

    # ---------------------------------------------------------
    # Ports
    # ---------------------------------------------------------

    elif "port" in q and ("listen" in q or "open" in q):
        candidate = make(
            "FU SUGGESTION",
            "You can inspect which process owns a specific listening port.",
            'fu "show what process is using port 8080"',
            "process-port",
        )

    # ---------------------------------------------------------
    # Docker
    # ---------------------------------------------------------

    elif "docker" in q:
        if current_rule == "docker-disk-usage":
            return None

        candidate = make(
            "FU SUGGESTION",
            "Inspect Docker disk usage before considering cleanup.",
            'fu "show docker disk usage"',
            "docker-disk-usage",
        )

    # ---------------------------------------------------------
    # Kubernetes fallback
    # ---------------------------------------------------------

    elif "pod" in q or "kubectl" in q or "kubernetes" in q:

        if current_rule == "k8s-pods-events":
            return None

        candidate = make(
            "FU SUGGESTION",
            "If a workload looks unhealthy, inspect pod status and "
            "recent events.",
            'fu "show kubernetes pods and recent events"',
            "k8s-pods-events",
        )

    else:
        return None

    # ---------------------------------------------------------
    # Universal loop guard
    # ---------------------------------------------------------

    if candidate.get("_next_rule") == current_rule:
        return None

    candidate.pop("_next_rule", None)
    return candidate

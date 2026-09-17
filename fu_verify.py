#!/usr/bin/env python3

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fu_history import load

WS = Path.home() / "Desktop" / "FU-Workspace"
VERIFY_STATE = WS / "sessions" / "verification-last.json"


def run(args, cwd=None, timeout=10):
    try:
        p = subprocess.run(
            args,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout
        )
        return p.returncode, p.stdout.strip()
    except Exception as e:
        return 1, str(e)


def verify_disk(row):
    rc, raw = run(["df", "-P", "/"])

    if rc != 0:
        return {
            "status": "UNKNOWN",
            "confidence": "LOW",
            "checks": [
                {
                    "ok": False,
                    "message": "Unable to read current root filesystem usage."
                }
            ],
        }

    lines = raw.splitlines()

    if len(lines) < 2:
        return {
            "status": "UNKNOWN",
            "confidence": "LOW",
            "checks": [
                {"ok": False, "message": "Unexpected df output."}
            ],
        }

    parts = lines[-1].split()

    try:
        pct = float(parts[4].rstrip("%"))
        avail_k = int(parts[3])
    except Exception:
        return {
            "status": "UNKNOWN",
            "confidence": "LOW",
            "checks": [
                {"ok": False, "message": "Could not parse df output."}
            ],
        }

    if pct < 85:
        state = "HEALTHY"
    elif pct < 90:
        state = "WATCH"
    else:
        state = "ATTENTION"

    return {
        "status": state,
        "confidence": "HIGH",
        "checks": [
            {
                "ok": True,
                "message": f"Current root filesystem usage is {pct:.1f}%."
            },
            {
                "ok": avail_k > 0,
                "message": f"Current root filesystem has {avail_k} KiB available."
            },
        ],
        "observed": {
            "root_usage_pct": pct,
            "available_kib": avail_k,
        },
    }


def verify_git(row):
    cwd = row.get("cwd")

    if not cwd:
        return {
            "status": "UNKNOWN",
            "confidence": "LOW",
            "checks": [{"ok": False, "message": "Original CWD unavailable."}],
        }

    rc, raw = run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=cwd
    )

    ok = rc == 0 and raw.strip() == "true"

    return {
        "status": "VERIFIED" if ok else "NOT VERIFIED",
        "confidence": "HIGH",
        "checks": [
            {
                "ok": ok,
                "message": (
                    f"{cwd} is inside a Git work tree."
                    if ok
                    else f"{cwd} is not inside a Git work tree."
                ),
            }
        ],
    }


def verify_last():
    rows = load()

    print()
    print("◆ FU VERIFY — LAST")
    print("─" * 88)

    if not rows:
        print("  No FU execution history available.")
        return

    row = rows[-1]
    rule = str(row.get("rule") or "")
    request = str(row.get("request") or "").lower()

    print(f"  Request      {row.get('request')}")
    print(f"  Command      {row.get('command')}")
    print(f"  Exit         {row.get('returncode')}")
    print()

    # Verification is deliberately rule-specific.
    if (
        "disk" in rule
        or "storage" in rule
        or "cleanup" in rule
        or "disk" in request
        or "storage" in request
        or "cleanup" in request
    ):
        result = verify_disk(row)

    elif rule in ("git-status", "git-log"):
        result = verify_git(row)

    else:
        result = {
            "status": "UNVERIFIED",
            "confidence": "LOW",
            "checks": [
                {
                    "ok": False,
                    "message": (
                        "No goal-specific verifier exists for this rule yet."
                    ),
                }
            ],
        }

    print("VERIFICATION")
    print("─" * 88)

    for check in result["checks"]:
        print(
            f"  {'✓' if check['ok'] else '○'} "
            f"{check['message']}"
        )

    print()
    print(f"  STATUS       {result['status']}")
    print(f"  CONFIDENCE   {result['confidence']}")

    if row.get("returncode") == 0:
        print()
        print(
            "  Command exit 0 is recorded separately from "
            "goal verification."
        )

    VERIFY_STATE.parent.mkdir(parents=True, exist_ok=True)

    VERIFY_STATE.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "history_index": len(rows) - 1,
                "history": row,
                "verification": result,
            },
            indent=2
        )
    )


def dispatch(argv):
    if not argv or argv[0].lower() != "verify":
        return False

    if len(argv) >= 2 and argv[1].lower() == "last":
        verify_last()
    else:
        print("Usage: fu verify last")

    return True

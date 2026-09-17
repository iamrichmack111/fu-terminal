#!/usr/bin/env python3

import json
from datetime import datetime, timezone
from pathlib import Path

WS = Path.home() / "Desktop" / "FU-Workspace"
HISTORY = WS / "sessions" / "history.jsonl"


def record(
    *,
    request,
    command,
    cwd,
    rule=None,
    source=None,
    risk=None,
    returncode=None,
    elapsed=None,
    log=None,
):
    HISTORY.parent.mkdir(parents=True, exist_ok=True)

    item = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request": request,
        "command": command,
        "cwd": str(cwd),
        "rule": rule,
        "source": source,
        "risk": risk,
        "returncode": returncode,
        "elapsed": elapsed,
        "log": str(log) if log else None,
    }

    try:
        with HISTORY.open("a") as f:
            f.write(json.dumps(item, separators=(",", ":")) + "\n")
    except Exception:
        # History must never break command execution.
        pass


def load():
    if not HISTORY.exists():
        return []

    rows = []

    try:
        for line in HISTORY.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        pass

    return rows


def show(rows):
    print()
    print("◆ FU HISTORY")
    print("─" * 88)

    if not rows:
        print("  No FU execution history recorded yet.")
        return

    for row in rows:
        rc = row.get("returncode")

        symbol = "✓" if rc == 0 else "✗"

        print()
        print(
            f"  {symbol} {row.get('timestamp', '?')}  "
            f"exit={rc}"
        )
        print(f"    REQUEST   {row.get('request')}")
        print(f"    COMMAND   {row.get('command')}")
        print(f"    CWD       {row.get('cwd')}")

        if row.get("rule"):
            print(f"    RULE      {row.get('rule')}")

        if row.get("risk"):
            print(f"    RISK      {row.get('risk')}")

        if row.get("elapsed") is not None:
            print(f"    ELAPSED   {row.get('elapsed'):.2f}s")


def incident_last():
    rows = load()

    print()
    print("◆ FU INCIDENT — LAST")
    print("─" * 88)

    if not rows:
        print("  No recorded FU execution.")
        return

    row = rows[-1]

    print(f"  Request      {row.get('request')}")
    print(f"  Command      {row.get('command')}")
    print(f"  CWD          {row.get('cwd')}")
    print(f"  Exit         {row.get('returncode')}")

    if row.get("returncode") == 0:
        print("  Execution    SUCCEEDED")
    else:
        print("  Execution    FAILED")

    verify_path = WS / "sessions" / "verification-last.json"
    verification = None

    if verify_path.exists():
        try:
            saved = json.loads(verify_path.read_text())

            saved_row = saved.get("history", {})

            # Verification belongs to this incident only when
            # the immutable execution fields match.
            same_execution = (
                saved_row.get("timestamp") == row.get("timestamp")
                and saved_row.get("command") == row.get("command")
                and saved_row.get("cwd") == row.get("cwd")
                and saved_row.get("returncode") == row.get("returncode")
            )

            if same_execution:
                verification = saved.get("verification")

        except Exception:
            verification = None

    if verification:
        print(
            f"  Verification "
            f"{verification.get('status', 'UNKNOWN')}"
        )
        print(
            f"  Confidence   "
            f"{verification.get('confidence', 'LOW')}"
        )

        checks = verification.get("checks", [])

        if checks:
            print()
            print("VERIFIED EVIDENCE")
            print("─" * 88)

            for check in checks:
                symbol = "✓" if check.get("ok") else "○"
                print(f"  {symbol} {check.get('message')}")

    else:
        print("  Verification NOT YET PERFORMED")

    print()
    print(
        "Execution success and goal verification are "
        "tracked separately."
    )


def dispatch(argv):
    if not argv:
        return False

    action = argv[0].lower()

    if action == "history":
        rows = load()

        count = 10

        if "--last" in argv:
            try:
                i = argv.index("--last")
                count = max(1, min(int(argv[i + 1]), 100))
            except Exception:
                print("Usage: fu history --last N")
                return True

        show(rows[-count:])
        return True

    if action == "incident":
        if len(argv) >= 2 and argv[1].lower() == "last":
            incident_last()
        else:
            print("Usage: fu incident last")

        return True

    return False

#!/usr/bin/env python3

import re


# Commands matching these patterns are considered intrinsically
# high-risk. Unknown/model-generated instances are hard blocked.
#
# An explicitly curated destructive KB rule may request approval,
# but may NEVER auto-execute.
DANGER_PATTERNS = [
    # Recursive / broad deletion
    r'(^|[;&|]\s*|\bsudo\s+)\brm\s+(?:[^\n;&|]*\s)?-[A-Za-z]*r[A-Za-z]*f[A-Za-z]*\b',
    r'(^|[;&|]\s*|\bsudo\s+)\brm\s+(?:[^\n;&|]*\s)?-[A-Za-z]*f[A-Za-z]*r[A-Za-z]*\b',

    # Filesystem creation/destruction
    r'(^|[;&|]\s*|\bsudo\s+)\bmkfs(?:\.[A-Za-z0-9_-]+)?\b',

    # Raw-device writes
    r'\bdd\b[^\n;&|]*\bof\s*=\s*/dev/',

    # Partitioning
    r'(^|[;&|]\s*|\bsudo\s+)\b(?:fdisk|cfdisk|sfdisk|parted)\b',

    # Power operations
    r'(^|[;&|]\s*|\bsudo\s+)\b(?:shutdown|reboot|poweroff|halt)\b',

    # Recursive ownership / permission changes
    r'(^|[;&|]\s*|\bsudo\s+)\bchmod\b[^\n;&|]*\s(?:-R|--recursive)\b',
    r'(^|[;&|]\s*|\bsudo\s+)\bchown\b[^\n;&|]*\s(?:-R|--recursive)\b',
    r'(^|[;&|]\s*|\bsudo\s+)\bchmod\b[^\n;&|]*(?:-R|--recursive)[^\n;&|]*',
    r'(^|[;&|]\s*|\bsudo\s+)\bchown\b[^\n;&|]*(?:-R|--recursive)[^\n;&|]*',

    # Download-and-execute pipelines
    r'\b(?:curl|wget)\b[^\n]*\|\s*(?:sudo\s+)?(?:bash|sh|zsh)\b',

    # Shell overwrite of block devices
    r'(?:>|>>)\s*/dev/(?:sd[a-z]|nvme\d+n\d+|vd[a-z]|xvd[a-z])(?:p?\d+)?\b',
]


def danger_reasons(command):
    """Return matching high-risk policy patterns. Never executes anything."""
    command = str(command or "")

    return [
        pattern
        for pattern in DANGER_PATTERNS
        if re.search(pattern, command, re.I | re.S)
    ]


def is_dangerous(command):
    return bool(danger_reasons(command))


def evaluate(command, source_type, metadata=None, auto_requested=False):
    """
    Pure FU execution-policy decision.

    Returns a dictionary only.
    It does NOT execute, prompt, modify files, or invoke a model.
    """
    metadata = metadata if isinstance(metadata, dict) else {}

    danger = is_dangerous(command)

    deterministic = source_type == "fastpath"
    curated = (
        deterministic
        and str(metadata.get("source", "")).lower() == "curated-kb"
    )

    risk = str(metadata.get("risk", "unknown")).lower()
    rule_auto = bool(metadata.get("auto", False))

    curated_destructive = (
        danger
        and curated
        and risk == "destructive"
        and not rule_auto
    )

    # Unknown/model-generated dangerous commands fail closed.
    if danger and not curated_destructive:
        return {
            "decision": "block",
            "allowed": False,
            "hard_block": True,
            "approval_required": False,
            "auto_allowed": False,
            "dangerous": True,
            "reason": (
                "High-risk command matched FU safety policy. "
                "Only explicitly curated destructive rules may request approval."
            ),
        }

    # Explicitly curated destructive rules may only request approval.
    if curated_destructive:
        return {
            "decision": "approval",
            "allowed": True,
            "hard_block": False,
            "approval_required": True,
            "auto_allowed": False,
            "dangerous": True,
            "reason": "Curated destructive operation requires explicit approval.",
        }

    # Only deterministic read-only rules explicitly marked auto may auto-run.
    auto_allowed = (
        auto_requested
        and deterministic
        and rule_auto
        and risk == "read"
    )

    if auto_allowed:
        return {
            "decision": "auto",
            "allowed": True,
            "hard_block": False,
            "approval_required": False,
            "auto_allowed": True,
            "dangerous": False,
            "reason": "Deterministic validated read-only rule may auto-run.",
        }

    # Everything else requires approval.
    return {
        "decision": "approval",
        "allowed": True,
        "hard_block": False,
        "approval_required": True,
        "auto_allowed": False,
        "dangerous": False,
        "reason": "Explicit approval required.",
    }

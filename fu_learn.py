#!/usr/bin/env python3

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TLDR = ROOT / "knowledge" / "sources" / "tldr"
CLF = ROOT / "knowledge" / "sources" / "commandlinefu.json"

RED = "\033[31m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

TOPICS = {
    "disk": [
        ("df", "Measure filesystem capacity and available space."),
        ("du", "Discover which files and directories consume space."),
        ("find", "Locate files by size, age, name, type, and more."),
        ("sort", "Rank diagnostic output."),
        ("stat", "Inspect detailed file and inode metadata."),
        ("lsof", "Inspect open files, including deleted-but-open files."),
    ],
    "storage": [
        ("df", "Measure filesystem capacity."),
        ("du", "Measure directory usage."),
        ("find", "Discover large or old files."),
        ("lsof", "Find open files consuming storage."),
        ("stat", "Inspect file and inode metadata."),
    ],
    "kubernetes": [
        ("kubectl", "Inspect and manage Kubernetes resources."),
        ("journalctl", "Inspect service logs such as k3s and kubelet."),
        ("watch", "Repeat diagnostic commands interactively."),
        ("df", "Check filesystem pressure."),
        ("ss", "Inspect sockets and listening services."),
    ],
    "docker": [
        ("docker", "Inspect containers, images, volumes, and daemon state."),
        ("du", "Inspect Docker storage directories."),
        ("journalctl", "Inspect Docker daemon logs."),
        ("ss", "Inspect published/listening ports."),
        ("ps", "Inspect container-related processes."),
    ],
    "networking": [
        ("ip", "Inspect interfaces, addresses, and routes."),
        ("ss", "Inspect sockets and listening ports."),
        ("ping", "Test network reachability."),
        ("curl", "Inspect HTTP services."),
        ("dig", "Inspect DNS."),
        ("traceroute", "Inspect network paths."),
    ],
    "git": [
        ("git", "Version-control fundamentals."),
        ("diff", "Understand textual differences."),
        ("ssh", "Understand remote authentication."),
    ],
    "linux": [
        ("find", "Filesystem discovery."),
        ("grep", "Search text."),
        ("sed", "Transform text streams."),
        ("awk", "Process structured text."),
        ("xargs", "Build commands from input."),
        ("ps", "Inspect processes."),
        ("ss", "Inspect sockets."),
        ("journalctl", "Inspect system logs."),
    ],
    "recovery": [
        ("lsof", "Find deleted files that are still open."),
        ("stat", "Understand inode and file metadata."),
        ("findmnt", "Identify filesystems and mount state."),
        ("lsblk", "Inspect block devices and filesystems."),
        ("dd", "Create raw images; potentially destructive if misused."),
        ("testdisk", "Filesystem/partition recovery tool."),
    ],
    "inode": [
        ("stat", "Inspect inode numbers, links, timestamps, and metadata."),
        ("ls", "Display inode numbers with ls -i."),
        ("find", "Search by inode with -inum."),
        ("lsof", "Connect open files to processes."),
        ("df", "Inspect inode exhaustion with df -i."),
    ],
    "deleted files": [
        ("lsof", "Find deleted files still held open by processes."),
        ("stat", "Understand inode/link metadata."),
        ("findmnt", "Identify the filesystem before recovery."),
        ("lsblk", "Inspect the backing block device."),
        ("testdisk", "Explore recovery tooling."),
    ],
}


RELATED = {
    "df": [
        ("du", "Find what is consuming the space."),
        ("findmnt", "Understand where filesystems are mounted."),
        ("lsblk", "Inspect the backing block devices."),
        ("lsof", "Find open/deleted files still consuming storage."),
    ],
    "du": [
        ("df", "Compare directory usage with filesystem capacity."),
        ("find", "Locate files by size or age."),
        ("sort", "Rank size results."),
        ("ncdu", "Explore disk usage interactively when installed."),
    ],
    "find": [
        ("xargs", "Turn search results into command arguments."),
        ("stat", "Inspect metadata for discovered files."),
        ("du", "Measure discovered paths."),
        ("grep", "Search file contents."),
    ],
    "lsof": [
        ("ps", "Inspect processes holding files."),
        ("stat", "Inspect file metadata."),
        ("findmnt", "Identify the underlying filesystem."),
        ("ss", "Inspect network sockets owned by processes."),
    ],
    "stat": [
        ("ls", "Inspect basic file metadata and inode numbers."),
        ("find", "Search for a specific inode."),
        ("df", "Inspect filesystem inode availability."),
        ("lsof", "Relate files to processes."),
    ],
    "kubectl": [
        ("journalctl", "Inspect node/service logs."),
        ("watch", "Repeat cluster observations."),
        ("jq", "Process Kubernetes JSON output."),
        ("curl", "Inspect Kubernetes/API endpoints."),
    ],
    "docker": [
        ("du", "Inspect Docker filesystem consumption."),
        ("journalctl", "Inspect Docker daemon logs."),
        ("ss", "Inspect exposed/listening ports."),
        ("ps", "Inspect related host processes."),
    ],
}

CONCEPTS = {
    "df": [
        "Filesystem capacity is different from directory size.",
        "Reserved filesystem blocks can make df percentages differ from simple used/total arithmetic.",
        "df -i measures inode consumption instead of data-block consumption.",
    ],
    "du": [
        "du walks directory trees and measures allocated storage.",
        "du and df answer different questions and can legitimately disagree.",
        "Deleted-but-open files can appear in df usage without appearing in ordinary du results.",
    ],
    "find": [
        "Tests such as -name, -type, -size and -mtime select filesystem objects.",
        "Actions such as -print and -exec operate on matches.",
        "-delete changes the filesystem and should be treated as destructive.",
        "-print0 combined with xargs -0 safely handles unusual filenames.",
    ],
    "lsof": [
        "Processes hold file descriptors independently of directory names.",
        "A deleted file can remain allocated while a process still has it open.",
        "lsof +L1 is useful for finding open files whose link count is below one.",
    ],
    "stat": [
        "An inode stores filesystem metadata; filenames are directory entries referring to inodes.",
        "Multiple filenames can refer to one inode through hard links.",
        "Removing the final directory link does not immediately destroy data if an open descriptor remains.",
    ],
    "findmnt": [
        "Recovery decisions depend on the actual filesystem and backing device.",
        "Identify the mount before considering filesystem-specific recovery tools.",
    ],
    "lsblk": [
        "Block devices, partitions, filesystems and mountpoints are separate layers.",
        "Recovery against the wrong device can cause severe damage.",
    ],
    "dd": [
        "dd copies byte streams and does not understand filesystem structure.",
        "Reversing input and output devices can destroy recoverable data.",
        "For recovery work, imaging a source before experimentation is generally safer than modifying the source.",
    ],
    "kubectl": [
        "kubectl queries and modifies objects through the Kubernetes API.",
        "get observes resources; describe adds detailed state/events; logs inspects workload output.",
        "Current node conditions should be distinguished from historical warning events.",
    ],
}

ADVANCED_RISK = {
    "dd": "HIGH-RISK TOOL — incorrect output targets can overwrite data.",
    "testdisk": "RECOVERY TOOL — inspect carefully before permitting writes.",
    "fsck": "FILESYSTEM TOOL — do not casually run against mounted writable filesystems.",
    "debugfs": "ADVANCED FILESYSTEM TOOL — write mode can alter filesystem structures.",
    "mount": "Mount options can change whether a filesystem is writable.",
}


def clean_placeholders(text):
    text = re.sub(r"\{\{\[([^\]|]+)\|[^\}]+\]\}\}", r"\1", text)
    text = re.sub(r"\{\{([^}]+)\}\}", r"<\1>", text)
    return text


def dangerous(command):
    patterns = [
        r"\brm\b",
        r"\b-delete\b",
        r"\bdd\b.*\bof=",
        r"\bmkfs\b",
        r"\bfsck\b",
        r"\bmount\b.*\s-o\s.*rw",
        r"\bchmod\b.*-R",
        r"\bchown\b.*-R",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bpoweroff\b",
        r"\bkill\b",
        r"\bpkill\b",
        r"\btruncate\b",
    ]
    return any(re.search(p, command, re.I) for p in patterns)


def tldr_path(command):
    candidates = [
        TLDR / "pages" / "linux" / f"{command}.md",
        TLDR / "pages" / "common" / f"{command}.md",
        TLDR / "pages" / "osx" / f"{command}.md",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def parse_tldr(command, limit=6):
    p = tldr_path(command)
    if not p:
        return None

    lines = p.read_text(errors="replace").splitlines()
    description = []
    examples = []
    pending = None

    for line in lines:
        if line.startswith("> ") and "More information:" not in line:
            description.append(line[2:].strip())

        elif line.startswith("- "):
            pending = line[2:].strip()

        elif pending and line.startswith("`") and line.endswith("`"):
            cmd = clean_placeholders(line.strip("`"))
            examples.append((pending, cmd, dangerous(cmd)))
            pending = None

    return {
        "path": str(p),
        "description": " ".join(description[:2]),
        "examples": examples[:limit],
    }


def man_text(command, lines=80):
    if not shutil.which("man"):
        return None
    p = subprocess.run(
        ["man", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env={**__import__("os").environ, "MANWIDTH": "90", "MANPAGER": "cat"},
    )
    if p.returncode:
        return None

    text = re.sub(r".\x08", "", p.stdout)
    return "\n".join(text.splitlines()[:lines]).strip()


def info_text(command, lines=80):
    if not shutil.which("info"):
        return None

    p = subprocess.run(
        ["info", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if p.returncode:
        return None

    return "\n".join(p.stdout.splitlines()[:lines]).strip()



def community_quality(command):
    """
    Community snippets are useful learning material, but age, platform
    assumptions and destructive behavior must be considered.
    """
    c = command.lower()

    suppress = [
        "/dev/mem",
        "/dev/kmem",
        "/dev/dsp",
        "arcfour",
        "telnet ",
        "ftp ",
        "python -m simplehttpserver",
    ]

    if any(x in c for x in suppress):
        return "legacy"

    if dangerous(command):
        return "review"

    risky = [
        "sudo ",
        "/dev/",
        "chmod 777",
        "| sh",
        "| bash",
    ]

    if any(x in c for x in risky):
        return "review"

    return "example"

def commandlinefu(command, limit=5):
    if not CLF.exists():
        return []

    try:
        data = json.loads(CLF.read_text())
    except Exception:
        return []

    token = command.lower().strip()
    rx = re.compile(r"(^|[|;&(]\s*|sudo\s+)" + re.escape(token) + r"(\s|$)")

    found = []
    for row in data:
        cmd = str(row.get("command", ""))
        summary = str(row.get("summary", "")).strip()

        if rx.search(cmd.lower()):
            try:
                votes = int(row.get("votes", 0))
            except Exception:
                votes = 0
            found.append((votes, summary, cmd, dangerous(cmd)))

    found.sort(key=lambda x: x[0], reverse=True)
    return found[:limit]


def docs_available(command):
    return {
        "tldr": bool(tldr_path(command)),
        "man": subprocess.run(
            ["man", "-w", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0 if shutil.which("man") else False,
        "info": subprocess.run(
            ["info", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0 if shutil.which("info") else False,
        "examples": bool(commandlinefu(command, 1)),
    }


def header(title):
    print()
    print(f"{BOLD}◆ {title}{RESET}")
    print("─" * 88)


def show_tldr(command):
    data = parse_tldr(command, 8)
    header(f"FU TLDR — {command.upper()}")

    if not data:
        print("No local English TLDR page found.")
        return

    if data["description"]:
        print(data["description"])
        print()

    for description, cmd, risky in data["examples"]:
        print(f"{BOLD}{description}{RESET}")
        if risky:
            print(f"  {YELLOW}⚠ REVIEW ONLY{RESET}  {cmd}")
        else:
            print(f"  {CYAN}{cmd}{RESET}")
        print()


def show_man(command):
    header(f"FU MAN — {command.upper()}")
    text = man_text(command, 120)
    print(text or "No local man page found.")


def show_info(command):
    header(f"FU INFO — {command.upper()}")
    text = info_text(command, 120)
    print(text or "No local GNU Info document found.")


def show_examples(command):
    header(f"FU COMMUNITY EXAMPLES — {command.upper()}")
    rows = commandlinefu(command, 8)

    if not rows:
        print("No matching local Commandlinefu examples found.")
        return

    print(f"{DIM}Community examples are secondary references; review before use.{RESET}\n")

    for votes, summary, cmd, risky in rows:
        flag = f"{YELLOW}⚠ REVIEW{RESET}" if risky else f"{GREEN}READ{RESET}"
        print(f"{flag}  votes={votes}")
        print(f"  {summary}")
        print(f"  {CYAN}{cmd}{RESET}")
        print()


def show_docs(command):
    header(f"FU DOCS — {command.upper()}")
    d = docs_available(command)

    for name in ("tldr", "man", "info", "examples"):
        mark = f"{GREEN}✓{RESET}" if d[name] else "·"
        print(f"  {mark} {name}")

    print()
    print(f"  Quick       {CYAN}fu tldr {command}{RESET}")
    print(f"  Standard    {CYAN}fu learn {command}{RESET}")
    print(f"  Reference   {CYAN}fu man {command}{RESET}")
    print(f"  Deep        {CYAN}fu info {command}{RESET}")
    print(f"  Community   {CYAN}fu examples {command}{RESET}")


def topic_commands(topic):
    topic = topic.lower().strip()
    return TOPICS.get(topic)


def show_topic(topic):
    commands = topic_commands(topic)

    if not commands:
        return False

    header(f"FU LEARN — {topic.upper()}")

    for command, purpose in commands:
        d = docs_available(command)
        sources = [
            name.upper()
            for name in ("tldr", "man", "info", "examples")
            if d[name]
        ]

        print(f"{BOLD}{command}{RESET}")
        print(f"  {purpose}")
        print(f"  Sources: {', '.join(sources) if sources else 'none detected'}")
        print(f"  → {CYAN}fu learn {command}{RESET}")
        print()

    return True



def show_deep(command):
    command = command.strip().lower()

    header(f"FU DEEP LEARN — {command.upper()}")

    risk = ADVANCED_RISK.get(command)
    if risk:
        print(f"{YELLOW}⚠ {risk}{RESET}")
        print()

    td = parse_tldr(command, 8)

    if td:
        if td["description"]:
            print(f"{BOLD}MENTAL MODEL{RESET}")
            print(td["description"])
            print()

        if td["examples"]:
            print(f"{BOLD}PRACTICAL PATTERNS{RESET}")

            for description, cmd, risky in td["examples"]:
                print()
                print(description)
                if risky:
                    print(f"  {YELLOW}⚠ REVIEW ONLY{RESET}  {cmd}")
                else:
                    print(f"  {CYAN}{cmd}{RESET}")

            print()

    concepts = CONCEPTS.get(command, [])

    if concepts:
        print(f"{BOLD}CORE CONCEPTS{RESET}")
        for concept in concepts:
            print(f"  • {concept}")
        print()

    m = man_text(command, 55)

    if m:
        print(f"{BOLD}LOCAL MAN REFERENCE{RESET}")
        print("\n".join(m.splitlines()[:35]))
        print()

    inf = info_text(command, 45)

    if inf:
        print(f"{BOLD}GNU INFO — DEEPER REFERENCE{RESET}")
        print("\n".join(inf.splitlines()[:28]))
        print()

    related = RELATED.get(command, [])

    if related:
        print(f"{BOLD}RELATED COMMANDS{RESET}")

        for other, reason in related:
            print(f"  {BOLD}{other}{RESET}")
            print(f"    {reason}")
            print(f"    → {CYAN}fu learn {other}{RESET}")

        print()

    community = [
        row for row in commandlinefu(command, 12)
        if community_quality(row[2]) != "legacy"
    ][:3]

    if community:
        print(f"{BOLD}COMMUNITY PATTERNS{RESET}")
        print(f"{DIM}Secondary references — inspect before use.{RESET}")

        for votes, summary, cmd, risky in community:
            print()
            quality = community_quality(cmd)

            if risky or quality == "review":
                flag = f"{YELLOW}⚠ REVIEW{RESET}"
            else:
                flag = f"{GREEN}SAFE EXAMPLE{RESET}"

            print(f"  {flag} · votes={votes}")
            print(f"  {summary}")
            print(f"  {CYAN}{cmd}{RESET}")

        print()

    print(f"{BOLD}CONTINUE{RESET}")
    print(f"  {CYAN}fu docs {command}{RESET}")

    for other, _ in related[:3]:
        print(f"  {CYAN}fu learn {other}{RESET}")

    print()
    print(f"{DIM}FU Deep Learn is educational and never executes examples automatically.{RESET}")

def show_learn(command):
    command = command.strip().lower()

    if show_topic(command):
        return

    header(f"FU LEARN — {command.upper()}")

    td = parse_tldr(command, 5)

    if td and td["description"]:
        print(f"{BOLD}QUICK IDEA{RESET}")
        print(td["description"])
        print()

    if td and td["examples"]:
        print(f"{BOLD}COMMON PATTERNS{RESET}")
        for description, cmd, risky in td["examples"]:
            print(f"\n{description}")
            if risky:
                print(f"  {YELLOW}⚠ REVIEW ONLY{RESET}  {cmd}")
            else:
                print(f"  {CYAN}{cmd}{RESET}")
        print()

    m = man_text(command, 25)
    if m:
        print(f"{BOLD}LOCAL MAN PAGE{RESET}")
        # Keep Learn compact; full page remains `fu man`.
        lines = m.splitlines()
        useful = []
        capture = False
        for line in lines:
            if line.strip() in ("NAME", "SYNOPSIS"):
                capture = True
            elif line.strip() == "DESCRIPTION" and useful:
                break
            if capture:
                useful.append(line)

        print("\n".join(useful[:18]).strip() or "\n".join(lines[:12]))
        print()

    d = docs_available(command)

    print(f"{BOLD}GO DEEPER{RESET}")
    if d["tldr"]:
        print(f"  {CYAN}fu tldr {command}{RESET}")
    if d["man"]:
        print(f"  {CYAN}fu man {command}{RESET}")
    if d["info"]:
        print(f"  {CYAN}fu info {command}{RESET}")
    if d["examples"]:
        print(f"  {CYAN}fu examples {command}{RESET}")

    print()
    print(f"{DIM}FU learning output never executes these examples automatically.{RESET}")


def explore_for_rule(rule):
    mapping = {
        "disk-doctor": "disk",
        "storage-opportunities": "storage",
        "cleanup-plan": "storage",
        "kubernetes-doctor": "kubernetes",
        "k8s-pods-events": "kubernetes",
        "docker-disk-usage": "docker",
        "ollama-doctor": "storage",
        "git-status": "git",
        "git-log": "git",
        "listening-ports": "networking",
        "network-connections": "networking",
    }
    return mapping.get(rule)



def print_used(rule):
    mapping = {
        "disk-doctor": [
            ("df", "Measured current filesystem capacity."),
            ("du", "Compared major storage areas."),
        ],
        "storage-opportunities": [
            ("du", "Measured reclaimable storage areas."),
            ("df", "Placed those sizes in filesystem context."),
        ],
        "cleanup-plan": [
            ("df", "Established the authoritative current filesystem usage."),
            ("du", "Measured candidate and review-only storage areas."),
        ],
        "kubernetes-doctor": [
            ("kubectl", "Read current Kubernetes resource and node state."),
        ],
        "k8s-pods-events": [
            ("kubectl", "Inspected workloads and Kubernetes events."),
        ],
        "docker-disk-usage": [
            ("docker", "Inspected Docker-managed storage."),
        ],
        "git-status": [
            ("git", "Inspected working-tree state."),
        ],
        "git-log": [
            ("git", "Inspected repository history."),
        ],
        "listening-ports": [
            ("ss", "Inspected listening sockets."),
        ],
        "network-connections": [
            ("ss", "Inspected network sockets."),
        ],
    }

    rows = mapping.get(rule)
    if not rows:
        return

    print()
    print(f"{BOLD}◆ WHAT YOU JUST USED{RESET}")
    print("─" * 88)

    for command, reason in rows:
        print(f"  {BOLD}{command}{RESET}")
        print(f"    {reason}")
        print(f"    → {CYAN}fu learn {command}{RESET}")
        print(f"    → {CYAN}fu learn {command} --deep{RESET}")
        print()

def print_explore(rule):
    topic = explore_for_rule(rule)
    if not topic:
        return

    commands = TOPICS.get(topic, [])[:4]

    print()
    print(f"{BOLD}◆ EXPLORE & LEARN{RESET}")
    print("─" * 88)

    for command, purpose in commands:
        print(f"  {BOLD}{command}{RESET}")
        print(f"    {purpose}")
        print(f"    → {CYAN}fu learn {command}{RESET}")
        print()

    print(f"  Topic → {CYAN}fu learn {topic}{RESET}")


def dispatch(argv):
    if len(argv) < 2:
        return False

    action = argv[0].lower()

    if action not in {"learn", "man", "info", "tldr", "examples", "docs"}:
        return False

    args = list(argv[1:])
    deep = False

    if "--deep" in args:
        deep = True
        args.remove("--deep")

    target = " ".join(args).strip()

    if not target:
        print(f"Usage: fu {action} COMMAND")
        return True

    if action == "learn":
        if deep:
            show_deep(target)
        else:
            show_learn(target)
    elif action == "man":
        show_man(target)
    elif action == "info":
        show_info(target)
    elif action == "tldr":
        show_tldr(target)
    elif action == "examples":
        show_examples(target)
    elif action == "docs":
        show_docs(target)

    return True


if __name__ == "__main__":
    import sys
    if not dispatch(sys.argv[1:]):
        print("Usage: fu_learn.py {learn|man|info|tldr|examples|docs} TARGET")

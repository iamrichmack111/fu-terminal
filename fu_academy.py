#!/usr/bin/env python3

import json
import random
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = Path.home() / "Desktop" / "FU-Workspace" / "sessions" / "academy-progress.json"

BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"

COURSES = {
    "filesystem": {
        "title": "Linux Filesystems",
        "lessons": [
            ("Filesystem capacity", "df", [
                "df measures filesystem-level capacity.",
                "df -h makes block usage human-readable.",
                "df -i measures inode usage instead of data blocks.",
                "df and du can disagree because they measure different things.",
            ]),
            ("Directory usage", "du", [
                "du walks directory trees and measures allocated storage.",
                "du -sh PATH summarizes one path.",
                "du -h --max-depth=1 PATH compares immediate children.",
                "Deleted-but-open files may consume space without appearing in ordinary du output.",
            ]),
            ("Inodes", "stat", [
                "A directory maps filenames to inode numbers.",
                "An inode stores metadata and references filesystem data.",
                "Hard links allow multiple names to reference one inode.",
                "stat exposes inode, link, size, owner, permission and timestamp information.",
            ]),
            ("Mounts and devices", "findmnt", [
                "A mount connects a filesystem to the directory tree.",
                "findmnt shows mount relationships.",
                "lsblk shows block devices, partitions and filesystems.",
                "Recovery decisions should begin by identifying the filesystem and device.",
            ]),
        ],
    },

    "shell": {
        "title": "Shell Fundamentals",
        "lessons": [
            ("Pipelines", "grep", [
                "The pipe operator sends stdout from one process to stdin of another.",
                "Small commands can be composed into larger workflows.",
                "Pipeline exit behavior matters when commands fail.",
                "FU itself uses pipefail when executing shell pipelines.",
            ]),
            ("Searching", "grep", [
                "grep searches text streams.",
                "grep -r searches recursively.",
                "grep -i ignores case.",
                "grep is commonly composed with ps, journalctl and other commands.",
            ]),
            ("Stream processing", "awk", [
                "awk processes records and fields.",
                "It is useful for extracting structured columns.",
                "awk programs can contain conditions and calculations.",
            ]),
            ("Argument construction", "xargs", [
                "xargs converts input into command arguments.",
                "NUL-delimited input is safer for arbitrary filenames.",
                "find -print0 and xargs -0 are a common combination.",
            ]),
        ],
    },

    "processes": {
        "title": "Linux Processes",
        "lessons": [
            ("Process inspection", "ps", [
                "Every process has a PID.",
                "ps reports process state and metadata.",
                "CPU and memory consumption can be ranked for diagnosis.",
            ]),
            ("Open resources", "lsof", [
                "Processes hold file descriptors.",
                "Descriptors can reference files, sockets and devices.",
                "Deleted files can remain allocated while descriptors remain open.",
                "lsof +L1 is useful for finding deleted-but-open files.",
            ]),
            ("Signals", "kill", [
                "Signals communicate events to processes.",
                "SIGTERM requests orderly termination.",
                "SIGKILL cannot be handled by the target process and should not be the first choice.",
            ]),
            ("Logs", "journalctl", [
                "systemd services commonly log to the journal.",
                "journalctl can filter by service, boot and time.",
                "Logs should generally be inspected before restarting a failing service.",
            ]),
        ],
    },

    "networking": {
        "title": "Linux Networking",
        "lessons": [
            ("Interfaces and routes", "ip", [
                "Interfaces have addresses and link state.",
                "Routes determine where packets are sent.",
                "ip replaces many older networking utilities.",
            ]),
            ("Sockets", "ss", [
                "Sockets connect processes to network endpoints.",
                "ss -l shows listening sockets.",
                "ss -tulpn is useful for service/port diagnosis when permissions allow.",
            ]),
            ("HTTP diagnosis", "curl", [
                "curl can inspect HTTP services without a browser.",
                "Response headers and status codes are useful diagnostic evidence.",
                "Verbose mode exposes connection and protocol details.",
            ]),
            ("DNS", "dig", [
                "DNS maps names to records.",
                "dig exposes DNS answers and resolver behavior.",
                "Name resolution problems should be separated from connectivity problems.",
            ]),
        ],
    },

    "systemd": {
        "title": "systemd & Services",
        "lessons": [
            ("Service state", "systemctl", [
                "systemctl queries and manages systemd units.",
                "status combines current state with recent information.",
                "Inspect before changing service state.",
            ]),
            ("Service logs", "journalctl", [
                "journalctl -u UNIT filters logs for one service.",
                "Boot filtering separates current and historical incidents.",
                "Historical errors do not necessarily describe current state.",
            ]),
        ],
    },

    "docker": {
        "title": "Docker Operations",
        "lessons": [
            ("Containers", "docker", [
                "Images are templates; containers are runtime instances.",
                "docker ps observes container state.",
                "Container state and host process state are related but not identical.",
            ]),
            ("Storage", "docker", [
                "Docker storage includes images, layers, containers, volumes and build cache.",
                "docker system df reports Docker-managed storage.",
                "Docker volumes may contain persistent application data.",
                "Cleanup should distinguish reclaimable cache from persistent data.",
            ]),
            ("Networking", "docker", [
                "Published ports map container services to host interfaces.",
                "Docker networks provide container connectivity.",
                "ss can verify what the host is actually listening on.",
            ]),
        ],
    },

    "kubernetes": {
        "title": "Kubernetes Troubleshooting",
        "lessons": [
            ("Observe first", "kubectl", [
                "Start troubleshooting by observing current state.",
                "kubectl get shows resource state.",
                "kubectl describe adds conditions and events.",
                "kubectl logs exposes workload output.",
            ]),
            ("Current vs historical", "kubectl", [
                "Events are historical observations.",
                "Current conditions describe present node/resource state.",
                "Old warnings should not override a recovered current condition.",
            ]),
            ("Node pressure", "df", [
                "DiskPressure can trigger Kubernetes eviction behavior.",
                "Host filesystem evidence should be correlated with Kubernetes conditions.",
                "Filesystem recovery should be verified after cleanup.",
            ]),
            ("Service diagnosis", "journalctl", [
                "k3s/kubelet/container runtime logs can explain node-level failures.",
                "Host logs complement Kubernetes API evidence.",
            ]),
        ],
    },

    "git": {
        "title": "Git Fundamentals",
        "lessons": [
            ("Working tree", "git", [
                "Git separates working tree, index and repository history.",
                "git status shows the relationship between them.",
            ]),
            ("Differences", "git", [
                "git diff shows unstaged differences.",
                "git diff --cached shows staged differences.",
                "Reviewing diffs before commits reduces accidental changes.",
            ]),
            ("History", "git", [
                "Commits form repository history.",
                "git log explores that history.",
                "Branches are movable references to commits.",
            ]),
        ],
    },

    "recovery": {
        "title": "Deleted File & Filesystem Recovery",
        "lessons": [
            ("Deletion model", "stat", [
                "A filename is a directory entry referencing an inode.",
                "Removing a name reduces the inode's link count.",
                "Blocks are not necessarily overwritten at the instant a filename is deleted.",
            ]),
            ("Deleted but open", "lsof", [
                "A process can keep a deleted inode alive through an open descriptor.",
                "lsof +L1 finds files with link counts below one.",
                "/proc/PID/fd/FD can expose an open descriptor on Linux.",
            ]),
            ("Identify storage", "findmnt", [
                "Determine the filesystem and backing device before recovery work.",
                "Recovery techniques differ across filesystems.",
                "Continued writes can reduce recovery chances after blocks become reusable.",
            ]),
            ("Image first", "dd", [
                "Raw-device tools operate below normal filesystem abstractions.",
                "Incorrect dd output targets can overwrite data.",
                "Recovery experimentation is safer on a copy/image when practical.",
                "FU never auto-executes raw recovery writes.",
            ]),
        ],
    },
}

QUIZZES = {
    "filesystem": [
        ("Which command reports filesystem capacity?", ["du", "df", "stat", "find"], 1),
        ("Which command reports inode usage with -i?", ["df", "grep", "ps", "ss"], 0),
        ("What does du primarily measure?", ["DNS", "directory/file usage", "CPU", "routes"], 1),
        ("What maps a filename to filesystem metadata?", ["socket", "inode", "PID", "signal"], 1),
    ],
    "shell": [
        ("What does | connect?", ["stderr to disk", "stdout to stdin", "RAM to swap", "two filesystems"], 1),
        ("Which pair safely handles unusual filenames?", ["find -print0 + xargs -0", "ls + grep", "cat + echo", "ps + kill"], 0),
        ("Which tool is designed around records and fields?", ["awk", "df", "ss", "stat"], 0),
    ],
    "networking": [
        ("Which command inspects sockets?", ["du", "ss", "stat", "find"], 1),
        ("Which tool is useful for HTTP diagnosis?", ["curl", "df", "awk", "kill"], 0),
        ("Which tool directly queries DNS?", ["dig", "ps", "du", "chmod"], 0),
    ],
    "docker": [
        ("Which command reports Docker-managed disk usage?", ["docker system df", "df -i", "git status", "ip route"], 0),
        ("Which Docker storage type commonly holds persistent app data?", ["volume", "PID", "signal", "route"], 0),
    ],
    "kubernetes": [
        ("Which is more authoritative for present node pressure?", ["an old event", "current node condition", "old log filename", "image tag"], 1),
        ("Which command adds conditions and events for a resource?", ["kubectl describe", "df", "git diff", "dig"], 0),
        ("DiskPressure is associated with what?", ["filesystem pressure", "DNS only", "Git history", "SSH keys"], 0),
    ],
    "recovery": [
        ("What should you check first for a recently deleted file still in use?", ["lsof +L1", "mkfs", "reboot", "rm -rf"], 0),
        ("What can continued writes do after deletion?", ["improve inode names", "reuse recoverable blocks", "restore filenames", "freeze the filesystem"], 1),
        ("Which command identifies mount/filesystem relationships?", ["findmnt", "grep", "ps", "curl"], 0),
        ("Why is dd treated as high risk?", ["it only reads text", "wrong output target can overwrite data", "it changes DNS", "it kills processes"], 1),
    ],
}


def load_state():
    STATE.parent.mkdir(parents=True, exist_ok=True)
    if not STATE.exists():
        return {"courses": {}, "quizzes": {}}
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"courses": {}, "quizzes": {}}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def header(title):
    print()
    print(f"{BOLD}◆ {title}{RESET}")
    print("─" * 88)


def list_courses():
    state = load_state()
    header("FU ACADEMY")

    for name, course in COURSES.items():
        done = state["courses"].get(name, {}).get("completed", [])
        total = len(course["lessons"])
        print(f"{BOLD}{name:<14}{RESET} {course['title']}")
        print(f"  Progress {len(done)}/{total}")
        print(f"  → {CYAN}fu course {name}{RESET}")
        if name in QUIZZES:
            print(f"  → {CYAN}fu quiz {name}{RESET}")
        print()


def course(name):
    name = name.lower().strip()

    if name not in COURSES:
        print(f"Unknown course: {name}")
        list_courses()
        return

    state = load_state()
    data = COURSES[name]
    completed = state["courses"].setdefault(name, {}).setdefault("completed", [])

    header(f"FU COURSE — {data['title'].upper()}")

    for i, (title, command, points) in enumerate(data["lessons"], 1):
        marker = f"{GREEN}✓{RESET}" if i in completed else "·"

        print(f"{marker} {BOLD}LESSON {i}: {title}{RESET}")
        for point in points:
            print(f"    • {point}")

        print(f"    Explore → {CYAN}fu learn {command}{RESET}")
        print(f"    Deep    → {CYAN}fu learn {command} --deep{RESET}")
        print()

    # Viewing a course counts as studying its lessons, but not quiz mastery.
    state["courses"][name]["last_viewed"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)

    print(f"{DIM}Mark a lesson complete with: fu complete {name} NUMBER{RESET}")


def complete(name, number):
    name = name.lower().strip()

    if name not in COURSES:
        print(f"Unknown course: {name}")
        return

    try:
        number = int(number)
    except ValueError:
        print("Lesson number must be numeric.")
        return

    total = len(COURSES[name]["lessons"])

    if not 1 <= number <= total:
        print(f"Lesson must be between 1 and {total}.")
        return

    state = load_state()
    completed = state["courses"].setdefault(name, {}).setdefault("completed", [])

    if number not in completed:
        completed.append(number)
        completed.sort()

    save_state(state)

    print(f"{GREEN}✓{RESET} Completed {name} lesson {number}")
    print(f"Progress: {len(completed)}/{total}")


def quiz(name):
    name = name.lower().strip()

    if name not in QUIZZES:
        print(f"No quiz available for: {name}")
        return

    questions = list(QUIZZES[name])
    random.shuffle(questions)

    header(f"FU QUIZ — {name.upper()}")

    score = 0

    for n, (question, choices, correct) in enumerate(questions, 1):
        print(f"{BOLD}{n}. {question}{RESET}")

        for i, choice in enumerate(choices, 1):
            print(f"   {i}. {choice}")

        try:
            answer = input("   Answer: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nQuiz cancelled.")
            return

        if answer == str(correct + 1):
            print(f"   {GREEN}✓ Correct{RESET}\n")
            score += 1
        else:
            print(f"   {YELLOW}→ {choices[correct]}{RESET}\n")

    pct = round(score / len(questions) * 100)

    state = load_state()
    previous = state["quizzes"].get(name, {}).get("best", 0)

    state["quizzes"][name] = {
        "last": pct,
        "best": max(previous, pct),
        "date": datetime.now().isoformat(timespec="seconds"),
    }

    save_state(state)

    header("RESULT")
    print(f"Score: {score}/{len(questions)} ({pct}%)")

    if pct == 100:
        print(f"{GREEN}Mastered this quiz set.{RESET}")
    elif pct >= 75:
        print("Good foundation. Review missed concepts and try again.")
    else:
        print("Review the course and related FU Learn pages before retrying.")


def progress():
    state = load_state()
    header("FU LEARNING PROGRESS")

    for name, course_data in COURSES.items():
        total = len(course_data["lessons"])
        done = len(state["courses"].get(name, {}).get("completed", []))
        quiz_data = state["quizzes"].get(name)

        q = f"{quiz_data['best']}%" if quiz_data else "—"

        print(f"{name:<14} lessons {done}/{total}   quiz best {q}")


def recommend():
    state = load_state()

    # Prioritize partially completed courses.
    for name, data in COURSES.items():
        completed = state["courses"].get(name, {}).get("completed", [])
        if completed and len(completed) < len(data["lessons"]):
            next_num = next(
                i for i in range(1, len(data["lessons"]) + 1)
                if i not in completed
            )

            header("FU RECOMMENDS")
            print(f"Continue {data['title']}: lesson {next_num}")
            print(f"→ {CYAN}fu course {name}{RESET}")
            return

    # Then courses with weak/no quiz mastery.
    for name in QUIZZES:
        best = state["quizzes"].get(name, {}).get("best", 0)
        if best < 75:
            header("FU RECOMMENDS")
            print(f"Study: {COURSES[name]['title']}")
            print(f"→ {CYAN}fu course {name}{RESET}")
            print(f"→ {CYAN}fu quiz {name}{RESET}")
            return

    header("FU RECOMMENDS")
    print("Explore a deeper Linux topic:")
    print(f"→ {CYAN}fu course filesystem{RESET}")
    print(f"→ {CYAN}fu learn inode --deep{RESET}")


def dispatch(argv):
    if not argv:
        return False

    action = argv[0].lower()

    if action == "academy":
        list_courses()
        return True

    if action == "course":
        if len(argv) < 2:
            list_courses()
        else:
            course(" ".join(argv[1:]))
        return True

    if action == "quiz":
        if len(argv) < 2:
            print("Usage: fu quiz TOPIC")
        else:
            quiz(" ".join(argv[1:]))
        return True

    if action == "complete":
        if len(argv) != 3:
            print("Usage: fu complete COURSE LESSON")
        else:
            complete(argv[1], argv[2])
        return True

    if action == "progress":
        progress()
        return True

    if action in ("next", "recommend"):
        recommend()
        return True

    return False


if __name__ == "__main__":
    import sys
    if not dispatch(sys.argv[1:]):
        list_courses()

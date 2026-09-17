#!/usr/bin/env python3

import re
import shlex
from pathlib import Path

BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"

# ----------------------------------------------------------------------
# Command knowledge
# ----------------------------------------------------------------------

COMMANDS = {
    "find": "Walk a directory tree and select matching filesystem objects.",
    "xargs": "Convert input into arguments for another command.",
    "du": "Measure file and directory storage usage.",
    "df": "Report filesystem capacity and available space.",
    "sort": "Sort lines of input.",
    "grep": "Search text for matching patterns.",
    "awk": "Process structured text as records and fields.",
    "sed": "Transform text streams.",
    "cut": "Extract selected fields or character ranges.",
    "head": "Show the beginning of a stream.",
    "tail": "Show the end of a stream.",
    "cat": "Read files and write their contents to standard output.",
    "tee": "Copy input to standard output and one or more files.",
    "wc": "Count lines, words, characters, or bytes.",
    "tr": "Translate or remove characters.",
    "stat": "Display detailed file or filesystem metadata.",
    "ls": "List directory contents and file metadata.",
    "lsof": "Show files and sockets held open by processes.",
    "ps": "Inspect running processes.",
    "ss": "Inspect network sockets.",
    "ip": "Inspect or configure Linux networking.",
    "curl": "Transfer data and inspect network/HTTP services.",
    "dig": "Query DNS.",
    "journalctl": "Read the systemd journal.",
    "systemctl": "Inspect or manage systemd units.",
    "docker": "Interact with the Docker engine.",
    "kubectl": "Interact with the Kubernetes API.",
    "git": "Interact with Git repositories.",
    "ssh": "Open a secure remote shell or execute remote commands.",
    "scp": "Copy files over SSH.",
    "rsync": "Synchronize files and directories.",
    "tar": "Create or extract archive files.",
    "gzip": "Compress or decompress gzip data.",
    "chmod": "Change file permission bits.",
    "chown": "Change file ownership.",
    "rm": "Remove filesystem entries.",
    "mv": "Move or rename filesystem entries.",
    "cp": "Copy files or directories.",
    "mkdir": "Create directories.",
    "touch": "Create a file or update timestamps.",
    "kill": "Send a signal to a process.",
    "pkill": "Send signals to processes selected by name/pattern.",
    "mount": "Attach a filesystem to the directory tree.",
    "umount": "Detach a mounted filesystem.",
    "findmnt": "Inspect filesystem mount relationships.",
    "lsblk": "Inspect block devices and filesystems.",
    "dd": "Copy raw byte streams between files or devices.",
    "sudo": "Run a command with elevated privileges.",
    "env": "Run a command with a modified environment.",
    "watch": "Repeat a command periodically and display its output.",
}

FLAGS = {
    ("find", "-type"): "Select objects by type.",
    ("find", "-name"): "Match filenames using a shell-style pattern.",
    ("find", "-iname"): "Match filenames case-insensitively.",
    ("find", "-size"): "Select files by size.",
    ("find", "-mtime"): "Select by modification age in days.",
    ("find", "-mmin"): "Select by modification age in minutes.",
    ("find", "-maxdepth"): "Limit recursive traversal depth.",
    ("find", "-mindepth"): "Require a minimum traversal depth.",
    ("find", "-print0"): "Emit NUL-separated paths so unusual filenames remain safe.",
    ("find", "-inum"): "Select filesystem objects by inode number.",
    ("find", "-delete"): "Delete matched filesystem objects.",

    ("xargs", "-0"): "Read NUL-separated input, commonly paired with find -print0.",
    ("xargs", "-n"): "Limit how many input arguments are passed per invocation.",
    ("xargs", "-P"): "Run multiple invocations in parallel.",

    ("du", "-h"): "Display human-readable sizes.",
    ("du", "-s"): "Show only a summary total.",
    ("du", "-x"): "Stay on the same filesystem.",
    ("du", "-d"): "Limit directory traversal depth.",
    ("du", "--max-depth"): "Limit directory traversal depth.",

    ("df", "-h"): "Display human-readable filesystem sizes.",
    ("df", "-i"): "Report inode usage instead of data-block usage.",
    ("df", "-T"): "Include filesystem type.",

    ("sort", "-h"): "Compare human-readable sizes such as K, M, and G.",
    ("sort", "-n"): "Compare values numerically.",
    ("sort", "-r"): "Reverse the result order.",
    ("sort", "-k"): "Sort using a selected field/key.",

    ("grep", "-i"): "Ignore letter case.",
    ("grep", "-r"): "Search directories recursively.",
    ("grep", "-R"): "Search recursively and follow symbolic links.",
    ("grep", "-n"): "Show matching line numbers.",
    ("grep", "-v"): "Invert the match.",
    ("grep", "-E"): "Use extended regular expressions.",

    ("lsof", "+L1"): "Show open files whose link count is below one, useful for deleted-but-open files.",
    ("lsof", "-i"): "Select network files/sockets.",

    ("ss", "-l"): "Show listening sockets.",
    ("ss", "-t"): "Show TCP sockets.",
    ("ss", "-u"): "Show UDP sockets.",
    ("ss", "-p"): "Show process information when permitted.",
    ("ss", "-n"): "Do not resolve service or host names.",

    ("ps", "aux"): "Show processes for all users with detailed resource information.",

    ("journalctl", "-u"): "Filter journal entries to a systemd unit.",
    ("journalctl", "-f"): "Follow new journal entries.",
    ("journalctl", "-b"): "Restrict output to a boot.",

    ("kubectl", "get"): "Retrieve Kubernetes resources.",
    ("kubectl", "describe"): "Show detailed resource state, conditions, and events.",
    ("kubectl", "logs"): "Read workload/container logs.",
    ("kubectl", "top"): "Display resource metrics when the metrics API is available.",

    ("docker", "ps"): "List containers.",
    ("docker", "images"): "List images.",
    ("docker", "logs"): "Read container logs.",
    ("docker", "system"): "Access Docker-wide management commands.",

    ("git", "status"): "Show working-tree and index state.",
    ("git", "log"): "Show commit history.",
    ("git", "diff"): "Show differences.",
    ("git", "add"): "Stage changes in the index.",
}

DANGEROUS = [
    (r"\brm\b.*\s-rf\b|\brm\s+-rf\b", "Recursive forced removal can permanently delete data."),
    (r"\bfind\b.*-delete\b", "find -delete removes every matched filesystem entry."),
    (r"\bdd\b.*\bof=/dev/", "Writing dd output to a block device can overwrite storage."),
    (r"\bmkfs(?:\.|\s)", "mkfs creates a filesystem and can destroy existing filesystem data."),
    (r"\bchmod\b.*-R\b", "Recursive permission changes can affect entire directory trees."),
    (r"\bchown\b.*-R\b", "Recursive ownership changes can affect entire directory trees."),
    (r"\bshutdown\b|\breboot\b|\bpoweroff\b", "This changes machine availability."),
    (r"\bkill\s+-9\b|\bpkill\s+-9\b", "SIGKILL immediately terminates matching processes."),
]

OPERATORS = {
    "|": (
        "PIPE",
        "Send standard output from the command on the left to standard input of the command on the right.",
    ),
    "||": (
        "OR",
        "Run the command on the right only when the command on the left fails.",
    ),
    "&&": (
        "AND",
        "Run the command on the right only when the command on the left succeeds.",
    ),
    ";": (
        "SEQUENCE",
        "Finish one command and then continue with the next.",
    ),
    ">": (
        "REDIRECT",
        "Replace a file with standard output from the preceding command.",
    ),
    ">>": (
        "APPEND",
        "Append standard output to a file.",
    ),
    "<": (
        "INPUT",
        "Use a file as standard input.",
    ),
    "2>": (
        "STDERR REDIRECT",
        "Redirect standard error to a file.",
    ),
    "2>&1": (
        "MERGE OUTPUT",
        "Send standard error to the same destination as standard output.",
    ),
}

# ----------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------

def header(title):
    print()
    print(f"{BOLD}◆ {title}{RESET}")
    print("─" * 88)


def shell_tokens(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>")
    lexer.whitespace_split = True
    lexer.commenters = ""

    try:
        raw = list(lexer)
    except ValueError:
        return command.split()

    # Recombine common redirection/operator forms.
    out = []
    i = 0

    while i < len(raw):
        if i + 2 < len(raw) and raw[i] == "2" and raw[i + 1] == ">" and raw[i + 2] == "&1":
            out.append("2>&1")
            i += 3
            continue

        if i + 1 < len(raw) and raw[i] == "2" and raw[i + 1] == ">":
            out.append("2>")
            i += 2
            continue

        out.append(raw[i])
        i += 1

    return out


def base_command(tokens):
    skip_next = False

    for token in tokens:
        if skip_next:
            skip_next = False
            continue

        if token in ("sudo", "command", "env", "nohup", "time"):
            continue

        if "=" in token and not token.startswith("-"):
            left = token.split("=", 1)[0]
            if left.replace("_", "").isalnum():
                continue

        if token.startswith("-"):
            continue

        return Path(token).name

    return None


def command_segments(tokens):
    segments = []
    current = []

    for token in tokens:
        if token in OPERATORS:
            if current:
                segments.append(("command", current))
                current = []
            segments.append(("operator", token))
        else:
            current.append(token)

    if current:
        segments.append(("command", current))

    return segments



def nested_commands(tokens):
    """
    Discover commands launched by wrappers/composition commands.

    Examples:
      xargs -0 du -h
      sudo du -sh /var
      env FOO=1 grep x file
      watch kubectl get pods
      command ls -la
      nohup python app.py
    """
    if not tokens:
        return []

    outer = Path(tokens[0]).name
    found = []

    wrappers = {
        "sudo",
        "env",
        "command",
        "nohup",
        "time",
        "watch",
    }

    # -----------------------------------------------------
    # Wrapper commands
    # -----------------------------------------------------

    if outer in wrappers:
        i = 1

        # Options belonging to wrappers that consume a value.
        wrapper_value_options = {
            "sudo": {
                "-u", "--user",
                "-g", "--group",
                "-h", "--host",
                "-p", "--prompt",
                "-C", "--close-from",
                "-T", "--command-timeout",
                "-R", "--chroot",
                "-D", "--chdir",
            },
            "env": {
                "-u", "--unset",
                "-C", "--chdir",
                "-S", "--split-string",
            },
            "watch": {
                "-n", "--interval",
                "-x", "--exec",
            },
        }

        takes_value = wrapper_value_options.get(outer, set())

        while i < len(tokens):
            token = tokens[i]

            # Environment assignments:
            # env LC_ALL=C sort -h
            if (
                "=" in token
                and not token.startswith("=")
                and not token.startswith("/")
            ):
                left = token.split("=", 1)[0]

                if left.replace("_", "").isalnum():
                    i += 1
                    continue

            if token == "--":
                i += 1
                break

            if token in takes_value:
                i += 2
                continue

            # Common attached option forms.
            if token.startswith("-") and token != "-":
                i += 1
                continue

            break

        if i < len(tokens):
            name = Path(tokens[i]).name

            # Record known commands. If the command isn't in our
            # description table yet, don't invent an explanation.
            if name in COMMANDS:
                found.append(name)

    # -----------------------------------------------------
    # xargs launches a command from input-generated args
    # -----------------------------------------------------

    if outer == "xargs":
        i = 1

        takes_value = {
            "-n", "--max-args",
            "-P", "--max-procs",
            "-I", "--replace",
            "-L", "--max-lines",
            "-s", "--max-chars",
            "-a", "--arg-file",
            "-E", "--eof",
        }

        while i < len(tokens):
            token = tokens[i]

            if token == "--":
                i += 1
                break

            if token in takes_value:
                i += 2
                continue

            if any(
                token.startswith(prefix) and token != prefix
                for prefix in (
                    "-n",
                    "-P",
                    "-I",
                    "-L",
                    "-s",
                    "-E",
                )
            ):
                i += 1
                continue

            if token.startswith("-"):
                i += 1
                continue

            break

        if i < len(tokens):
            name = Path(tokens[i]).name

            if name in COMMANDS:
                found.append(name)

    return list(dict.fromkeys(found))


def explain_nested(tokens):
    nested = nested_commands(tokens)

    if not nested:
        return []

    print()
    print(f"  {BOLD}NESTED COMMAND{RESET}")

    for command in nested:
        print(f"  {CYAN}{command}{RESET}")
        print(f"    {COMMANDS.get(command, 'Command executed by the outer command.')}")

        # Explain flags belonging to the nested command.
        try:
            start = next(
                i for i, token in enumerate(tokens)
                if Path(token).name == command
            )
        except StopIteration:
            continue

        for token in tokens[start + 1:]:
            explanation = FLAGS.get((command, token))

            if explanation:
                print(f"    {CYAN}{token}{RESET}")
                print(f"      {explanation}")

    return nested

def explain_segment(tokens):
    if not tokens:
        return

    cmd = base_command(tokens)

    if not cmd:
        print("  " + " ".join(tokens))
        return

    print(f"{BOLD}{cmd}{RESET}")
    print(f"  {COMMANDS.get(cmd, 'Execute this command as part of the shell expression.')}")

    # Show sudo separately.
    if "sudo" in tokens:
        print(f"  {YELLOW}sudo{RESET}")
        print("    Execute with elevated privileges.")

    # Explain recognized subcommands and flags.
    i = 0

    while i < len(tokens):
        token = tokens[i]

        explanation = FLAGS.get((cmd, token))

        if explanation:
            print(f"  {CYAN}{token}{RESET}")
            print(f"    {explanation}")

            # Common options taking one argument.
            if token in {
                "-name", "-iname", "-size", "-mtime", "-mmin",
                "-maxdepth", "-mindepth", "-inum", "-d",
                "--max-depth", "-n", "-P", "-k", "-u"
            }:
                if i + 1 < len(tokens):
                    value = tokens[i + 1]
                    print(f"    Value: {value}")
                    i += 1

        elif token.startswith("-") and token not in ("-", "--"):
            print(f"  {DIM}{token}{RESET}")
            print("    Option passed to this command.")

        elif i > 0 and token not in ("sudo", cmd):
            # Avoid repeating recognized subcommands.
            if FLAGS.get((cmd, token)) is None:
                if token.startswith("/"):
                    print(f"  {CYAN}{token}{RESET}")
                    print("    Filesystem path.")
                elif token not in OPERATORS:
                    print(f"  {DIM}{token}{RESET}")
                    print("    Argument/value.")

        i += 1


def concepts_for(commands, command):
    concepts = []

    if "|" in command:
        concepts.append("pipeline composition")

    if "&&" in command or "||" in command:
        concepts.append("conditional shell execution")

    if ">" in command:
        concepts.append("I/O redirection")

    if "find" in commands:
        concepts.append("filesystem traversal and predicates")

    if "xargs" in commands:
        concepts.append("argument construction")

    if "grep" in commands or "awk" in commands or "sed" in commands:
        concepts.append("stream/text processing")

    if "df" in commands or "du" in commands:
        concepts.append("storage diagnosis")

    if "lsof" in commands or "ps" in commands:
        concepts.append("process/resource inspection")

    if "ss" in commands or "ip" in commands or "curl" in commands or "dig" in commands:
        concepts.append("network diagnosis")

    if "kubectl" in commands:
        concepts.append("Kubernetes API inspection")

    if "docker" in commands:
        concepts.append("container operations")

    if "git" in commands:
        concepts.append("version-control state")

    if "-print0" in command and "xargs" in commands and "-0" in command:
        concepts.append("NUL-safe filename handling")

    return list(dict.fromkeys(concepts))


def risks(command):
    found = []

    for pattern, explanation in DANGEROUS:
        if re.search(pattern, command, re.I):
            found.append(explanation)

    return found


def explain(command):
    command = command.strip()

    header("FU WHY")

    print(f"{BOLD}COMMAND{RESET}")
    print(f"  {CYAN}{command}{RESET}")

    found_risks = risks(command)

    if found_risks:
        print()
        print(f"{RED}⚠ SAFETY REVIEW{RESET}")
        for item in found_risks:
            print(f"  • {item}")

    tokens = shell_tokens(command)
    segments = command_segments(tokens)

    commands = []

    print()
    print(f"{BOLD}BREAKDOWN{RESET}")
    print()

    for kind, value in segments:
        if kind == "operator":
            title, explanation = OPERATORS[value]
            print(f"{YELLOW}{value}  [{title}]{RESET}")
            print(f"  {explanation}")
            print()
            continue

        cmd = base_command(value)

        if cmd and cmd not in commands:
            commands.append(cmd)

        explain_segment(value)

        for nested in explain_nested(value):
            if nested not in commands:
                commands.append(nested)

        print()

    concepts = concepts_for(commands, command)

    if concepts:
        print(f"{BOLD}CONCEPTS{RESET}")
        for concept in concepts:
            print(f"  • {concept}")
        print()

    if commands:
        print(f"{BOLD}EXPLORE{RESET}")

        for cmd in commands:
            if cmd in COMMANDS:
                print(f"  {CYAN}fu learn {cmd}{RESET}")
                print(f"  {CYAN}fu learn {cmd} --deep{RESET}")

        print()

    print(f"{DIM}FU Why explains commands only. It never executes the supplied command.{RESET}")



LAST_COMMAND = (
    Path.home()
    / "Desktop"
    / "FU-Workspace"
    / "sessions"
    / "last-command.txt"
)


def save_last(command):
    """Persist FU's most recently successful executed command."""
    try:
        LAST_COMMAND.parent.mkdir(parents=True, exist_ok=True)
        LAST_COMMAND.write_text(command.strip() + "\n")
    except Exception:
        # Learning metadata must never break normal FU execution.
        pass


def explain_last():
    if not LAST_COMMAND.exists():
        header("FU EXPLAIN LAST")
        print("No successfully executed FU command has been recorded yet.")
        print()
        print(f"Run a normal FU command first, then:")
        print(f"  {CYAN}fu explain-last{RESET}")
        return

    command = LAST_COMMAND.read_text().strip()

    if not command:
        print("No previous FU command is available.")
        return

    header("FU EXPLAIN LAST")
    print(f"{DIM}Most recent successfully executed FU command:{RESET}")
    print(f"  {CYAN}{command}{RESET}")

    explain(command)

def dispatch(argv):
    if not argv:
        return False

    action = argv[0].lower()

    if action in ("explain-last", "why-last"):
        explain_last()
        return True

    if action != "why":
        return False

    if len(argv) < 2:
        print("Usage: fu why 'COMMAND'")
        return True

    explain(" ".join(argv[1:]))
    return True


if __name__ == "__main__":
    import sys
    dispatch(sys.argv[1:])

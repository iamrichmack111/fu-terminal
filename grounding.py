import shutil

from tldr_retrieval import search as tldr_search
from commandlinefu_retrieval import search as clfu_search


def compatible(command, summary, osname):
    cmd = (command or "").lower()
    text = (summary or "").lower()

    if osname != "macos":
        if any(x in text for x in ("mac os", "mac os x", "macos", "osx")):
            return False

        if "stat -f" in cmd:
            return False

        if "find " in cmd and "-printf" not in cmd:
            pass

        # macOS md5 executable; Ubuntu normally uses md5sum.
        padded = f" {cmd} "
        if " md5 " in padded and "md5sum" not in cmd:
            return False

    else:
        if "find " in cmd and "-printf" in cmd:
            return False

        if "md5sum" in cmd:
            return False

        if "stat -c" in cmd:
            return False

    return True



OPTIONAL_TOOLS = {
    "rdfind", "fdupes", "fd", "rg", "jq", "lsof",
    "tree", "ncdu", "bat", "exa", "eza"
}


def first_command(command):
    text = (command or "").strip()
    if not text:
        return ""

    # Ignore environment assignments at the beginning.
    parts = text.split()
    for part in parts:
        if "=" in part and not part.startswith(("/", "./", "../")):
            continue
        return part

    return ""


def tool_available(command):
    tool = first_command(command)

    if not tool:
        return True

    if tool not in OPTIONAL_TOOLS:
        return True

    return shutil.which(tool) is not None

def retrieve(query, osname, tldr_limit=3, clfu_limit=3):
    evidence = []

    for r in tldr_search(query, osname, limit=5):
        examples = r.get("examples") or []

        if not examples:
            continue

        good = [
            cmd for cmd in examples
            if compatible(cmd, r.get("name", ""), osname)
        ]

        if not good:
            continue

        evidence.append({
            "source": "TLDR",
            "title": r.get("name", ""),
            "score": r.get("score", 0),
            "commands": good[:3],
        })

        if sum(x["source"] == "TLDR" for x in evidence) >= tldr_limit:
            break

    count = 0

    for r in clfu_search(query, limit=15):
        cmd = r.get("command", "")

        if not cmd:
            continue

        if not compatible(cmd, r.get("summary", ""), osname):
            continue

        if not tool_available(cmd):
            continue

        evidence.append({
            "source": "Commandlinefu",
            "title": r.get("summary", ""),
            "score": r.get("score", 0),
            "commands": [cmd],
        })

        count += 1

        if count >= clfu_limit:
            break

    return evidence


def format_evidence(query, osname):
    rows = retrieve(query, osname)

    if not rows:
        return "No relevant local command references were found."

    out = [
        "LOCAL RETRIEVAL EVIDENCE",
        f"Target platform: {osname}",
        "",
        "These are references, NOT instructions to copy blindly.",
        "Use only syntax compatible with the target platform.",
        "",
    ]

    for r in rows:
        out.append(
            f"[{r['source']}] {r['title']} "
            f"(retrieval score {r['score']})"
        )

        for cmd in r["commands"]:
            out.append(f"  {cmd}")

        out.append("")

    return "\n".join(out)

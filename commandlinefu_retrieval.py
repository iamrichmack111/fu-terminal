import json
import re
from pathlib import Path

DB = Path(__file__).resolve().parent / "knowledge" / "sources" / "commandlinefu.json"

STOP = {
    "a", "an", "the", "me", "my", "show", "give", "get", "please",
    "how", "to", "in", "on", "of", "for", "with", "using", "all",
    "from", "and", "or", "is", "are", "that", "this", "i", "want"
}

ALIASES = {
    "duplicate": ["duplicates", "md5", "checksum"],
    "duplicates": ["duplicate", "md5", "checksum"],
    "files": ["file", "find"],
    "file": ["files", "find"],
    "ports": ["port", "listen", "netstat", "ss", "lsof"],
    "processes": ["process", "ps", "pid"],
    "disk": ["du", "df", "space"],
    "memory": ["ram", "free"],
    "network": ["ip", "netstat", "ss"],
}

_cache = None


def tokens(text):
    return {
        x
        for x in re.findall(r"[a-z0-9_.+-]+", text.lower())
        if len(x) > 1 and x not in STOP
    }


def load():
    global _cache

    if _cache is None:
        if not DB.exists():
            return []
        _cache = json.loads(DB.read_text())

    return _cache


def search(query, limit=5):
    q = tokens(query)

    expanded = set(q)
    for word in q:
        expanded.update(ALIASES.get(word, []))

    scored = []

    for item in load():
        summary = (item.get("summary") or "").lower()
        command = (item.get("command") or "").lower()

        summary_words = tokens(summary)
        command_words = tokens(command)

        score = 0

        # Original query words get strongest weighting.
        score += len(q & summary_words) * 12
        score += len(q & command_words) * 5

        # Aliases are useful but weaker evidence.
        score += len(expanded & summary_words) * 4
        score += len(expanded & command_words) * 2

        # Exact phrase in description gets a large bonus.
        phrase = query.lower().strip()
        if phrase and phrase in summary:
            score += 30

        # Votes only act as a small tiebreaker.
        try:
            votes = int(item.get("votes") or 0)
        except (TypeError, ValueError):
            votes = 0

        score += min(max(votes, 0), 100) / 50

        if score >= 8:
            scored.append((score, item))

    scored.sort(key=lambda x: -x[0])

    return [
        {
            "score": round(score, 1),
            **item,
        }
        for score, item in scored[:limit]
    ]


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:])

    for result in search(query):
        print()
        print(f"[{result['score']}] {result.get('summary', '')}")
        print("   ", result["command"])

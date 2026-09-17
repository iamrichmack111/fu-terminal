import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TLDR = ROOT / "knowledge" / "sources" / "tldr" / "pages"

STOP = {
    "a","an","the","me","my","show","give","get","please","how","to",
    "in","on","of","for","with","using","all","from","and","or","is",
    "are","that","this","i","want"
}

ALIASES = {
    "files": ["find", "file"],
    "file": ["find"],
    "ports": ["ss", "lsof", "netstat"],
    "connections": ["ss", "netstat"],
    "processes": ["ps", "top", "pgrep"],
    "disk": ["du", "df"],
    "memory": ["free", "vmstat"],
    "network": ["ip", "ss"],
    "containers": ["docker"],
    "kubernetes": ["kubectl"],
    "k8s": ["kubectl"],
    "archive": ["tar"],
    "archives": ["tar"],
    "compress": ["gzip", "xz", "zip"],
    "duplicates": ["fdupes", "rdfind", "find"],
    "duplicate": ["fdupes", "rdfind", "find"],
}

_index = None

def words(text):
    return [
        x for x in re.findall(r"[a-z0-9_.+-]+", text.lower())
        if len(x) > 1 and x not in STOP
    ]

def build_index(osname="linux"):
    global _index

    if _index is not None:
        return _index

    platforms = ["common"]
    platforms.append("osx" if osname == "macos" else "linux")

    docs = []

    for platform in platforms:
        base = TLDR / platform
        if not base.exists():
            continue

        for path in base.glob("*.md"):
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue

            docs.append({
                "name": path.stem.lower(),
                "platform": platform,
                "path": str(path),
                "text": text,
                "lower": text.lower(),
            })

    _index = docs
    return docs

def search(query, osname="linux", limit=5):
    qwords = words(query)

    expanded = set(qwords)
    for w in qwords:
        expanded.update(ALIASES.get(w, []))

    scored = []

    for doc in build_index(osname):
        score = 0
        name = doc["name"]
        text = doc["lower"]

        for w in expanded:
            if w == name:
                score += 30
            elif w in name:
                score += 12

            if f"`{w}" in text:
                score += 5

            score += min(text.count(w), 5)

        if doc["platform"] != "common":
            score += 1

        if score:
            scored.append((score, doc))

    scored.sort(key=lambda x: (-x[0], x[1]["name"]))

    results = []

    for score, doc in scored[:limit]:
        examples = []

        for line in doc["text"].splitlines():
            line = line.strip()
            if line.startswith("`") and line.endswith("`"):
                examples.append(line[1:-1])

            if len(examples) >= 5:
                break

        results.append({
            "score": score,
            "name": doc["name"],
            "platform": doc["platform"],
            "path": doc["path"],
            "examples": examples,
        })

    return results

if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:])

    for result in search(query):
        print(f"\n[{result['score']}] {result['name']} ({result['platform']})")
        for example in result["examples"]:
            print("   ", example)

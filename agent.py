#!/usr/bin/env python3
import os,re,sys,json,shutil,platform,subprocess
from suggestions import suggest
from output_analysis import analyze, print_analysis
import fu_ui as ui
import time
from pathlib import Path
from datetime import datetime
import requests
from retrieval import lookup as kb_lookup
from tldr_retrieval import search as tldr_search
from commandlinefu_retrieval import search as clfu_search
from grounding import format_evidence
import signal
from fu_learn import dispatch as learn_dispatch, print_explore, print_used
from fu_academy import dispatch as academy_dispatch
from fu_why import dispatch as why_dispatch, save_last
from fu_safety import evaluate as safety_evaluate
from fu_evidence import dispatch as evidence_dispatch
from fu_history import dispatch as history_dispatch, record as history_record
from fu_verify import dispatch as verify_dispatch
from fu_investigate import dispatch as investigate_dispatch

OLLAMA=os.getenv("OLLAMA_HOST","http://127.0.0.1:11434").rstrip("/")
WS=Path(os.getenv("FU_WORKSPACE", str(Path.home()/"Desktop"/"FU-Workspace"))).expanduser()

DEFAULT_MODEL=os.getenv("FU_MODEL", "qwen2.5-coder:3b")
MODELS={
 "shell":[DEFAULT_MODEL],
 "devops":[DEFAULT_MODEL],
 "coding":[DEFAULT_MODEL],
 "security":[DEFAULT_MODEL]
}

DANGER=[
 r'\brm\s+-rf\b',r'\bmkfs\b',r'\bdd\s+.*\bof=',
 r'\bfdisk\b',r'\bparted\b',r'\bshutdown\b',r'\breboot\b',
 r'\bpoweroff\b',r'\bchmod\s+-R\b',r'\bchown\s+-R\b',
 r'\bcurl\b.*\|\s*(sudo\s+)?(ba)?sh\b',
 r'\bwget\b.*\|\s*(sudo\s+)?(ba)?sh\b'
]

SEC={"nmap","nikto","ffuf","gobuster","sqlmap","hydra","pentest",
     "vulnerability","recon","tcpdump","tshark","hashcat","john"}
DEV={"docker","kubernetes","kubectl","k3s","helm","terraform","ansible",
     "systemctl","journalctl","nginx","traefik","container","pod","deployment"}
CODE={"python","javascript","typescript","flask","django","react","angular",
      "ruby","rails","golang","rust","code","script","function","html","css"}

AUTO = False

def host():
    s=platform.system()
    return {
      "os":"macos" if s=="Darwin" else "ubuntu" if Path("/etc/os-release").exists() and "ubuntu" in Path("/etc/os-release").read_text().lower() else s.lower(),
      "arch":platform.machine(),
      "shell":Path(os.getenv("SHELL","unknown")).name,
      "sed":"BSD sed (sed -i '')" if s=="Darwin" else "GNU sed (sed -i)",
      "package_manager":"brew" if s=="Darwin" else "apt"
    }

def topic(q):
    q=q.lower()
    scores={
      "security":sum(x in q for x in SEC),
      "devops":sum(x in q for x in DEV),
      "coding":sum(x in q for x in CODE)
    }
    k=max(scores,key=scores.get)
    return k if scores[k] else "shell"

def ask(model,prompt):
    r=requests.post(OLLAMA+"/api/generate",json={
      "model":model,
      "prompt":prompt,
      "stream":False,
      "keep_alive":0,
      "options":{"temperature":0.1,"num_ctx":8192}
    },timeout=240)
    r.raise_for_status()
    return r.json()["response"].strip()

def extract(x):
    b=re.findall(r"```(?:bash|sh|shell)?\s*\n(.*?)```",x,re.S|re.I)
    return "\n\n".join(b).strip() if b else x.strip()

def syntax(cmd):
    p=subprocess.run(["bash","-n"],input=cmd,text=True,
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    return p.returncode==0,p.stderr

def platform_validate(cmd):
    """Reject placeholders and common cross-platform mistakes before approval."""
    h = host()
    problems = []

    # Model-generated placeholders are not executable commands.
    # Reject them mechanically rather than asking the user to notice them.
    placeholder_checks = [
        (r'\{\{[^\n{}]+\}\}',
         "unresolved template placeholder such as {{path/to/file}}"),

        (r'(?<![<])<(?:file|filename|directory|dir|path|folder|command|name|user|username|host|hostname|port|url)>(?![>])',
         "unresolved angle-bracket placeholder"),

        (r'(?<![A-Za-z0-9_])/(?:path|your/path|some/path)/to(?:/|\b)',
         "unresolved example path"),

        (r'\b(?:YOUR|REPLACE_WITH|INSERT|EXAMPLE)_[A-Z0-9_]+\b',
         "unresolved symbolic placeholder"),
    ]

    for pattern, reason in placeholder_checks:
        if re.search(pattern, cmd, re.I | re.M):
            problems.append(reason)

    if h["os"] == "macos":
        checks = [
            (r'\bfind\b[^\n]*\s-printf\b',
             "macOS BSD find does not support -printf; use stat -f or another BSD-compatible form"),

            (r'(^|[;&|]\s*)apt(?:-get)?\s',
             "apt is a Debian/Ubuntu package manager; this host uses Homebrew"),

            (r'\bsystemctl\b',
             "systemctl/systemd is normally unavailable on macOS; use launchctl or the service-specific mechanism"),

            (r'\bjournalctl\b',
             "journalctl is a systemd command and is not the normal macOS logging interface"),


            (r'\breadlink\s+-f\b',
             "macOS BSD readlink does not provide GNU readlink -f"),

            (r'\bstat\s+(?:-[^-][^\n]*\s)?-c\b',
             "macOS uses BSD stat; GNU stat -c is incompatible"),

            (r'\bdate\s+[^\n]*-d(?:\s|$)',
             "macOS BSD date does not support GNU date -d"),

            (r'\bgrep\s+[^\n]*-P\b',
             "the default macOS grep does not support GNU grep -P"),
        ]

    elif h["os"] in ("ubuntu", "linux"):
        checks = [
            (r'\bbrew\s+(?:install|uninstall|upgrade)\b',
             "Homebrew command generated for a Linux/Ubuntu host"),

            (r'\blaunchctl\b',
             "launchctl is a macOS command"),

            (r'\bpbcopy\b|\bpbpaste\b',
             "pbcopy/pbpaste are macOS commands"),

            (r'\bopen\s+-a\b',
             "open -a is macOS-specific"),

            (r'\bdiskutil\b',
             "diskutil is macOS-specific"),

            (r'\bdefaults\s+(?:read|write|delete)\b',
             "defaults is macOS-specific"),

            (r"\bsed\s+-i\s+(['\"])\1\s",
             "sed -i '' is BSD/macOS syntax; GNU sed normally uses sed -i"),
        ]
    else:
        checks = []

    for pattern, reason in checks:
        if re.search(pattern, cmd, re.I | re.M):
            problems.append(reason)

    # Check obvious executable names where practical.
    lines = [
        x.strip() for x in cmd.splitlines()
        if x.strip() and not x.lstrip().startswith("#")
    ]

    return len(problems) == 0, problems


def fastmeta(command, rule_id, risk="read", auto=False, source="builtin-fastpath"):
    """Create a deterministic FU command with explicit execution metadata."""
    return {
        "command": command,
        "source": source,
        "id": rule_id,
        "risk": risk,
        "auto": bool(auto),
    }


def fastpath(req):
    """Deterministic commands for common terminal requests."""
    import re

    q = req.lower().strip()
    h = host()
    osname = h.get("os", "").lower()

    hit = kb_lookup(req, osname)
    if hit:
        return {
            "command": hit["command"],
            "source": "curated-kb",
            "id": hit.get("id", "unknown"),
            "risk": hit.get("risk", "unknown"),
            "auto": bool(hit.get("auto", False)),
        }

    # ---- FILES ---------------------------------------------------------

    # N largest files in Downloads
    m = re.search(r'(?:show|find|list|give).*?(\d+).*?largest files.*?downloads', q)
    if not m:
        m = re.search(r'(\d+)\s+largest files.*?downloads', q)

    if m:
        n = max(1, min(int(m.group(1)), 100))

        if osname == "macos":
            return (
                f'find "$HOME/Downloads" -type f '
                f'-exec stat -f \'%z %N\' {{}} + | '
                f'sort -nr | head -n {n}'
            )

        return (
            f'find "$HOME/Downloads" -type f '
            f'-printf \'%s %p\\n\' | sort -nr | head -n {n}'
        )

    # Disk usage
    if any(x in q for x in [
        "disk space",
        "disk usage",
        "free disk",
        "how much disk",
    ]):
        return fastmeta('df -h', "disk-usage", risk="read", auto=True)

    # Largest directories in current directory
    if "largest directories" in q or "largest folders" in q:
        return fastmeta(
            'du -sh ./* 2>/dev/null | sort -hr | head -n 10',
            "largest-directories",
            risk="read",
            auto=True
        )

    # ---- SYSTEM --------------------------------------------------------

    if "memory usage" in q or "ram usage" in q:
        if osname == "macos":
            return fastmeta('vm_stat', "memory-usage", risk="read", auto=True)
        return fastmeta('free -h', "memory-usage", risk="read", auto=True)

    if "cpu info" in q or "cpu information" in q:
        if osname == "macos":
            return fastmeta('sysctl -n machdep.cpu.brand_string', "cpu-info", risk="read", auto=True)
        return fastmeta('lscpu', "cpu-info", risk="read", auto=True)

    if "hostname" in q and not any(x in q for x in ["change", "set", "rename"]):
        return fastmeta('hostname', "hostname", risk="read", auto=True)

    if "ip address" in q or "my ip" in q:
        if osname == "macos":
            return fastmeta('ifconfig', "network-addresses", risk="read", auto=True)
        return fastmeta('ip addr', "network-addresses", risk="read", auto=True)

    # ---- PROCESSES -----------------------------------------------------

    if "top processes" in q or "processes using most cpu" in q:
        return fastmeta(
            'ps aux --sort=-%cpu | head -n 11'
            if osname != "macos"
            else 'ps aux | sort -nrk 3 | head -n 11',
            "top-cpu-processes",
            risk="read",
            auto=True
        )

    if "processes using most memory" in q or "top memory processes" in q:
        return fastmeta(
            'ps aux --sort=-%mem | head -n 11'
            if osname != "macos"
            else 'ps aux | sort -nrk 4 | head -n 11',
            "top-memory-processes",
            risk="read",
            auto=True
        )

    # ---- NETWORK -------------------------------------------------------

    if "listening ports" in q or "open ports" in q:
        if osname == "macos":
            return fastmeta('lsof -nP -iTCP -sTCP:LISTEN', "listening-ports", risk="read", auto=True)
        return fastmeta('ss -lntup', "listening-ports", risk="read", auto=True)

    if "network connections" in q:
        if osname == "macos":
            return fastmeta('netstat -an', "network-connections", risk="read", auto=True)
        return fastmeta('ss -tunap', "network-connections", risk="read", auto=True)

    # ---- DOCKER --------------------------------------------------------

    if "docker containers" in q or "running containers" in q:
        return fastmeta('docker ps', "docker-containers", risk="read", auto=True)

    if "docker images" in q:
        return fastmeta('docker images', "docker-images", risk="read", auto=True)

    if "docker disk usage" in q:
        return fastmeta('docker system df', "docker-disk-usage", risk="read", auto=True)

    # ---- KUBERNETES ----------------------------------------------------

    if "kubernetes pods" in q or "k8s pods" in q:
        return fastmeta('kubectl get pods -A', "kubernetes-pods", risk="read", auto=True)

    if "kubernetes nodes" in q or "k8s nodes" in q:
        return fastmeta('kubectl get nodes -o wide', "kubernetes-nodes", risk="read", auto=True)

    if "kubernetes services" in q or "k8s services" in q:
        return fastmeta('kubectl get svc -A', "kubernetes-services", risk="read", auto=True)

    # ---- GIT -----------------------------------------------------------

    if q in ("git status", "show git status") or "repository status" in q:
        return fastmeta('git status', "git-status", risk="read", auto=True)

    if "recent git commits" in q or "recent commits" in q:
        return fastmeta('git log --oneline -n 10', "git-log", risk="read", auto=True)

    return None


def generate(req,error=""):

    osname = host()["os"].lower()

    # Highest-trust / cheapest route first.
    # Do NOT search TLDR/Commandlinefu when the curated KB or
    # deterministic fastpath already knows the answer.
    quick = fastpath(req)
    if quick:
        print("⚡ FU fastpath", file=sys.stderr)

        if isinstance(quick, dict):
            return "fastpath", quick, quick["command"]

        # Legacy deterministic rule without explicit metadata.
        # Never silently auto-execute an unclassified command.
        meta = {
            "source": "builtin-fastpath",
            "id": "legacy-unclassified",
            "risk": "unknown",
            "auto": False,
        }
        return "fastpath", meta, quick

    # Curated/deterministic miss: now search the larger reference corpus.
    retrieval_context = format_evidence(req, osname)

    t=topic(req)
    h=host()
    for m in MODELS[t]:
        print(f"→ {t} → {m}",file=sys.stderr)

        previous_error = ""
        if error:
            previous_error = "IMPORTANT: A previous model was mechanically REJECTED. Do NOT repeat its command.\n" + error[-5000:]

        prompt=f"""You are FU, a local terminal command generator.

HOST={json.dumps(h)}
WORKSPACE={WS}
REQUEST={req}


CRITICAL RETRIEVAL RULES:
- Retrieved TLDR and Commandlinefu commands are REFERENCE MATERIAL ONLY.
- NEVER concatenate multiple retrieved examples into the answer.
- Return exactly ONE coherent shell command or ONE necessary pipeline.
- Do not output alternative commands.
- Do not output multiple approaches.
- Do not blindly copy placeholders from retrieval examples.
- Resolve ordinary user locations explicitly.
- "Downloads" means "$HOME/Downloads".
- "Desktop" means "$HOME/Desktop".
- "Documents" means "$HOME/Documents".
- Never interpret those as relative to the FU workspace.
- Prefer standard commands already present on the target OS.
- Do not use rdfind, fdupes, fd, rg, jq, lsof, tree, or other optional utilities unless FU confirms they are installed.
- On Ubuntu use GNU syntax.
- On macOS use BSD/macOS syntax.
- For read-only requests, do not modify, delete, hardlink, symlink, move, or overwrite files.
- A request to FIND duplicates means report duplicates only; never deduplicate them.
- Produce ONLY the final shell command inside one bash code block.

LOCAL COMMAND REFERENCES:
{retrieval_context}

Previous execution error, if any:
{previous_error}

Rules:
- Generate ONLY commands appropriate for this host.
- This host uses {h['sed']}.
- On macOS, BSD find DOES NOT support -printf.
- On macOS, use stat -f when file size/metadata is needed.
- On macOS use Homebrew rather than apt.
- On macOS use launchctl rather than systemctl where applicable.
- Never repeat a command that the validator rejected.
- Generate the MINIMUM commands necessary for the request.
- Do not create directories or cd into the workspace for read-only questions.
- New projects belong under {WS}/projects.
- Prefer quoted heredocs for substantial file creation.
- Prefer sed for small deterministic edits.
- Never claim commands executed.
- Never include secrets.
- Return executable shell commands in ONE bash code block.
"""
        try:
            out=ask(m,prompt)
            cmd=extract(out)
            ok,syntax_error=syntax(cmd)
            if not ok:
                print(f"  rejected shell syntax: {syntax_error.strip()}", file=sys.stderr)
                continue

            platform_ok, platform_errors = platform_validate(cmd)

            if not platform_ok:
                reason = "; ".join(platform_errors)
                print(f"  rejected for {h['os']}: {reason}", file=sys.stderr)

                correction = ""

                if h["os"] == "macos" and "find does not support -printf" in reason:
                    correction = """
KNOWN MACOS CORRECTION:
BSD find has no -printf.

For file sizes use this pattern:
find "$HOME/Downloads" -type f -exec stat -f '%z %N' {} +

For the 10 largest files:
find "$HOME/Downloads" -type f -exec stat -f '%z %N' {} + | sort -nr | head -n 10

Do NOT use find -printf.
Do NOT add mkdir, cd, sed, or unrelated commands.
"""

                error = (
                    "The previous command was mechanically rejected.\n"
                    f"HOST: {h['os']}\n"
                    f"REASON: {reason}\n"
                    f"REJECTED COMMAND:\n{cmd}\n"
                    + correction
                )
                continue

            if cmd:
                return t,m,cmd
        except Exception as e:
            print(f"  fallback: {e}",file=sys.stderr)
    print("\nFU: every model produced a command that failed validation.", file=sys.stderr)
    print("No command was executed.", file=sys.stderr)
    return None, None, None

def doctor():
    print("FU LOCAL AGENT\n")
    for k,v in host().items(): print(f"{k:16} {v}")
    print(f"{'workspace':16} {WS}")
    try:
        data=requests.get(OLLAMA+"/api/tags",timeout=5).json()
        installed={x["name"] for x in data.get("models",[])}
        print("\nMODEL CASCADE")
        for m in dict.fromkeys(sum(MODELS.values(),[])):
            print(("✓" if m in installed else "✗"),m)
    except Exception as e:
        print("Ollama error:",e)

def run(req):
    error = ""

    # Commands should execute where the user invoked FU,
    # not inside FU's private workspace.
    caller_cwd = Path(
        os.environ.get("FU_CALLER_CWD", str(Path.cwd()))
    ).expanduser().resolve()

    while True:
        started_generation = time.perf_counter()
        t, m, cmd = generate(req, error)
        generation_time = time.perf_counter() - started_generation

        if not cmd:
            ui.fail("No valid command generated.")
            return

        h = host()

        ui.logo()
        ui.header("FU DRY RUN")

        print()
        print(" ", ui.c(req, ui.BOLD))
        print()

        ui.badge("Platform", f"{h['os']} {h['arch']}", ui.CYAN)

        if t == "fastpath" and isinstance(m, dict):
            source_name = (
                "CURATED KB"
                if m.get("source") == "curated-kb"
                else "BUILT-IN FASTPATH"
            )

            risk = str(m.get("risk", "unknown")).upper()
            auto_allowed = bool(m.get("auto", False)) and risk == "READ"

            ui.badge("Source", source_name, ui.GREEN)

            if m.get("id") and m.get("id") != "builtin":
                ui.badge("Rule", m["id"], ui.CYAN)

            ui.badge(
                "Mode",
                "AUTO" if AUTO and auto_allowed else "APPROVAL",
                ui.YELLOW if AUTO and auto_allowed else ui.CYAN
            )

            ui.badge(
                "Risk",
                f"{risk} / VALIDATED",
                ui.GREEN if risk == "READ" else ui.YELLOW
            )
        else:
            auto_allowed = False
            ui.badge("Source", f"{t} / {m}", ui.PURPLE)
            ui.badge("Mode", "APPROVAL REQUIRED", ui.YELLOW)
            ui.badge("Risk", "MODEL GENERATED", ui.YELLOW)

        ui.step("Command resolved", generation_time)
        ui.step("Platform validated")
        ui.step("Shell syntax validated")

        ui.command_box(cmd)

        # -----------------------------------------------------
        # CENTRAL FU SAFETY POLICY
        #
        # This exact pure policy is also exercised by selftest.
        # Dangerous test strings never reach subprocess execution.
        # -----------------------------------------------------

        safety = safety_evaluate(
            command=cmd,
            source_type=t,
            metadata=m if isinstance(m, dict) else None,
            auto_requested=AUTO,
        )

        if safety["hard_block"]:
            ui.blocked(safety["reason"])
            return

        if safety["dangerous"] and safety["approval_required"]:
            ui.warn(
                "DESTRUCTIVE curated operation — explicit approval is required."
            )

        if safety["auto_allowed"]:
            ui.auto()
            choice = "y"
        else:
            choice = ui.approval()

        if choice in ("", "n"):
            ui.warn("Cancelled")
            return

        if choice == "r":
            continue

        if choice == "e":
            f = WS / "generated" / "pending-command.sh"
            f.write_text(cmd + "\n")

            subprocess.run([os.getenv("EDITOR", "nano"), str(f)])
            cmd = f.read_text()

            ok, err = syntax(cmd)

            if not ok:
                ui.fail(err)
                continue

            platform_ok, platform_errors = platform_validate(cmd)

            if not platform_ok:
                ui.fail("Platform validation failed")
                for problem in platform_errors:
                    print("   -", problem)
                continue

        if choice not in ("y", "e"):
            continue

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log = WS / "logs" / f"{stamp}.log"

        print()
        print(ui.c("LIVE OUTPUT", ui.BOLD))
        print(ui.c(ui.line(), ui.GRAY))

        execution_started = time.perf_counter()

        p = subprocess.Popen(
            ["bash", "-o", "pipefail", "-lc", cmd],
            cwd=caller_cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1
        )

        output = []

        try:
            with log.open("w") as lf:
                pipe_closed = False

                for line in p.stdout:
                    if not pipe_closed:
                        try:
                            print(line, end="", flush=True)
                        except BrokenPipeError:
                            # Downstream consumer (head/grep/etc.) exited.
                            # Continue draining and logging the child process
                            # without crashing FU.
                            pipe_closed = True

                    lf.write(line)
                    lf.flush()
                    output.append(line)

            p.wait()

        except KeyboardInterrupt:
            print()
            ui.warn("Interrupted by user")
            p.terminate()

            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()

        elapsed = time.perf_counter() - execution_started
        full_output = "".join(output)

        ui.result(p.returncode, elapsed, log)

        # Structured FU execution history.
        # Recording must not affect command success/failure semantics.
        if isinstance(m, dict):
            history_record(
                request=req,
                command=cmd,
                cwd=caller_cwd,
                rule=m.get("id"),
                source=m.get("source", t),
                risk=m.get("risk"),
                returncode=p.returncode,
                elapsed=elapsed,
                log=log,
            )
        else:
            history_record(
                request=req,
                command=cmd,
                cwd=caller_cwd,
                source=t,
                risk="model-generated",
                returncode=p.returncode,
                elapsed=elapsed,
                log=log,
            )

        if p.returncode == 0:
            analysis = analyze(m.get("id"), full_output, p.returncode)
            if analysis:
                print_analysis(analysis)

            suggestion = None if analysis else suggest(
                req,
                full_output,
                p.returncode,
                current_rule=m.get("id")
            )

            if suggestion:
                print()
                ui.header(suggestion["title"])
                print()
                print(" ", suggestion["message"])

                if suggestion.get("next"):
                    print()
                    print(" ", ui.c("TRY NEXT", ui.GRAY))
                    print(" ", ui.c(suggestion["next"], ui.CYAN))


            # Contextual learning companion.
            # Educational only: never executes suggested examples.
            if p.returncode == 0:
                # Record only commands FU actually executed successfully.
                # Dry runs, cancelled commands and failed commands are excluded.
                save_last(cmd)

                if isinstance(m, dict):
                    print_used(m.get("id"))
                    print_explore(m.get("id"))

            return

        # Deterministic commands will resolve to the same command again.
        # Do not enter a pointless regeneration loop.
        if t == "fastpath":
            ui.warn("Deterministic command failed; regeneration skipped.")

            if m.get("id") in ("git-status", "git-log"):
                print()
                print("  FU hint: run this command from inside a Git repository.")

            return

        if input("\nGenerate correction? [y/N] ").lower().strip() != "y":
            return

        error = full_output


def main():
    argv = sys.argv[1:]

    # FU reliability test suite. Local-only; never model generated.
    if argv and argv[0].lower() in ("selftest", "self-test"):
        import fu_selftest
        return

    # -----------------------------------------------------
    # LOCAL DETERMINISTIC INTERFACES
    #
    # These MUST run before retrieval/model generation.
    # They never execute the command being studied.
    # -----------------------------------------------------

    # Explain shell commands deterministically.
    if evidence_dispatch(argv):
        return

    if history_dispatch(argv):
        return

    if verify_dispatch(argv):
        return

    if investigate_dispatch(argv):
        return

    if why_dispatch(argv):
        return

    # FU Academy: courses, quizzes and progress.
    if academy_dispatch(argv):
        return
    # Guided FU courses.
    if len(sys.argv) >= 3 and sys.argv[1].lower() == "course":
        course = " ".join(sys.argv[2:]).lower().strip()

        if course in ("recovery", "deleted files", "file recovery"):
            import fu_recovery
            fu_recovery.lesson()
            return

        print(f"Unknown FU course: {course}")
        print("Available: recovery")
        return

    # FU's local learning/documentation interface.
    # Handles:
    #   fu learn find
    #   fu man find
    #   fu info find
    #   fu tldr find
    #   fu examples find
    #   fu docs find
    if learn_dispatch(argv):
        return

    # ---------------------------------------------------------
    # RESERVED FU COMMAND GUARD
    #
    # FU-native commands must NEVER fall through to an LLM.
    # A missing/not-yet-implemented subsystem fails closed.
    # ---------------------------------------------------------
    reserved_fu_commands = {
        "why",
        "why-last",
        "explain-last",
        "learn",
        "docs",
        "man",
        "info",
        "tldr",
        "examples",
        "academy",
        "course",
        "quiz",
        "complete",
        "progress",
        "next",
        "recommend",
        "selftest",
        "self-test",

        # Reliability v2 namespace.
        "evidence",
        "history",
        "incident",
        "verify",
        "investigate",
    }

    if argv and argv[0].lower() in reserved_fu_commands:
        command_name = argv[0].lower()

        print()
        print("◆ FU LOCAL SUBSYSTEM")
        print("─" * 88)
        print(f"  `{command_name}` is reserved for FU's local deterministic subsystem.")
        print("  The requested local action is not currently available.")
        print()
        print("  NO MODEL FALLBACK")
        print("  NO COMMAND EXECUTED")
        return

    global AUTO

    # Behave like a normal Unix CLI when output is piped to
    # head, grep, less, etc. and the downstream process exits.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    for x in ["projects","generated","backups","logs","sessions"]:
        (WS/x).mkdir(parents=True,exist_ok=True)

    args = sys.argv[1:]

    if "--auto" in args:
        AUTO = True
        args.remove("--auto")

    if not args:
        print('fu "request"')
        print('fu --auto "request"')
        print('fu doctor')
        return

    if args[0] == "doctor":
        doctor()
        return

    if args[0] == "search":
        query = " ".join(args[1:])

        if not query:
            print('Usage: fu search "query"')
            return

        osname = host()["os"].lower()

        tldr_results = tldr_search(query, osname, limit=5)
        clfu_results = clfu_search(query, limit=10)

        # Filter obvious cross-platform Commandlinefu results.
        filtered_clfu = []

        for r in clfu_results:
            summary = (r.get("summary") or "").lower()
            command = (r.get("command") or "").lower()

            if osname != "macos":
                if any(x in summary for x in [
                    "mac os",
                    "mac os x",
                    "macos",
                    "osx"
                ]):
                    continue

                # Common BSD/macOS-specific forms.
                if "stat -f" in command:
                    continue

                if " md5 " in f" {command} " and "md5sum" not in command:
                    continue

            if osname == "macos":
                # Obvious GNU/Linux-specific constructs.
                if "find " in command and "-printf" in command:
                    continue

                if "md5sum" in command:
                    continue

                if "stat -c" in command:
                    continue

            filtered_clfu.append(r)

            if len(filtered_clfu) >= 5:
                break

        print("\n" + "=" * 68)
        print("FU KNOWLEDGE SEARCH")
        print("=" * 68)
        print("Query   :", query)
        print("Platform:", osname)

        print("\nTLDR")
        print("=" * 68)

        if not tldr_results:
            print("No TLDR matches.")
        else:
            for r in tldr_results:
                print(f"\n{r['name']} [{r['platform']}] score={r['score']}")
                for example in r["examples"]:
                    print("  ", example)

        print("\nCOMMANDLINEFU")
        print("=" * 68)

        if not filtered_clfu:
            print("No compatible Commandlinefu matches.")
        else:
            for r in filtered_clfu:
                print(f"\n[{r['score']}] {r.get('summary', '')}")
                print("  ", r["command"])

        return

    run(" ".join(args))

if __name__=="__main__":
    main()

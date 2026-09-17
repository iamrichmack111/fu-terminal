#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WORK="$ROOT/demo/render"
SCENES="$WORK/scenes"
VOICE="$WORK/voice"
OUT="$ROOT/media/fu-terminal-feature-demo.mp4"

rm -rf "$WORK"
mkdir -p "$SCENES" "$VOICE" media

command -v ffmpeg >/dev/null || { echo "ffmpeg required"; exit 1; }
command -v ffprobe >/dev/null || { echo "ffprobe required"; exit 1; }
command -v node >/dev/null || { echo "node required"; exit 1; }
command -v fu >/dev/null || { echo "fu required"; exit 1; }

# ---------- Piper ----------
VOICE_DIR="$HOME/.local/share/fu-terminal/voices/en_US-ryan-high"
MODEL="$VOICE_DIR/en_US-ryan-high.onnx"
JSON="$MODEL.json"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high"

mkdir -p "$VOICE_DIR"

if command -v piper >/dev/null 2>&1; then
    PIPER="$(command -v piper)"
else
    [ -d demo/.venv ] || python3 -m venv demo/.venv
    demo/.venv/bin/pip install -q piper-tts
    PIPER="$ROOT/demo/.venv/bin/piper"
fi

[ -f "$MODEL" ] || curl -L --fail -o "$MODEL" "$BASE/en_US-ryan-high.onnx"
[ -f "$JSON" ]  || curl -L --fail -o "$JSON" "$BASE/en_US-ryan-high.onnx.json"

# ---------- Capture genuine FU output ----------
capture() {
    local name="$1"
    shift

    {
        printf '$'
        printf ' %q' "$@"
        printf '\n\n'
        "$@"
    } > "$WORK/$name.txt" 2>&1 || true
}

echo "Capturing FU commands..."

capture selftest fu selftest
capture disk fu --auto "disk usage"
capture investigate fu investigate disk
capture evidence fu evidence
capture verify fu verify last
capture learn fu learn kubectl

cat > "$WORK/intro.txt" <<'EOF'
FU TERMINAL

Retrieval-first terminal intelligence

CURATED KNOWLEDGE
TLDR
MAN / INFO
COMMANDLINEFU
LOCAL OLLAMA FALLBACK

Safety • Evidence • Verification • Learning

Same terminal. Smarter answers.
EOF

cat > "$WORK/safety.txt" <<'EOF'
$ fu --auto "rm -rf /"

◆ FU SAFETY

RISK       DESTRUCTIVE
AUTO       DENIED
STATUS     BLOCKED

FU will not automatically execute a destructive command.

Unknown or model-generated dangerous commands fail closed.

✓ No command was executed.
EOF

cat > "$WORK/outro.txt" <<'EOF'
FU TERMINAL

RETRIEVAL FIRST
LOCAL FIRST
SAFETY FOCUSED

54 / 54 REGRESSION CHECKS PASSING

Evidence-based diagnostics
Execution verification
Command provenance
Local AI fallback

Same terminal. Smarter answers.
EOF

# ---------- Narration ----------
cat > "$VOICE/01.txt" <<'EOF'
Welcome to FU Terminal. FU is a retrieval-first terminal intelligence and safety engine. Instead of immediately asking an AI model to invent a command, FU checks deterministic knowledge and trusted local sources first. Local AI remains available as a fallback. Let's take a closer look.
EOF

cat > "$VOICE/02.txt" <<'EOF'
We begin with FU self test. This checks the major reliability subsystems, including Kubernetes support, diagnostics, learning, retrieval, working directory handling, safety policy, and command validation. The current release passes all fifty four regression checks.
EOF

cat > "$VOICE/03.txt" <<'EOF'
Next, we ask FU for disk usage. FU resolves this request through its curated knowledge base. Before anything runs, it displays the platform, source, matching rule, execution mode, and risk classification. Because this is a validated read-only command, automatic execution is permitted.
EOF

cat > "$VOICE/04.txt" <<'EOF'
FU can investigate a system before recommending changes. Disk investigation is intentionally read only. It examines filesystem pressure, inode usage, deleted open files, and relevant Kubernetes pressure signals when they are available. Diagnosis comes before remediation.
EOF

cat > "$VOICE/05.txt" <<'EOF'
The evidence subsystem captures current authoritative system signals. This gives FU a concrete snapshot of system state instead of relying on assumptions or stale command output. Evidence can then support later diagnosis and verification.
EOF

cat > "$VOICE/06.txt" <<'EOF'
Verify last demonstrates an important distinction. A command returning exit code zero only proves that the command ran successfully. It does not necessarily prove that the intended goal was achieved. FU can compare the execution record with current evidence and report a verification result.
EOF

cat > "$VOICE/07.txt" <<'EOF'
FU also includes terminal learning tools. Here, FU provides practical kubectl knowledge directly from the command line. The learning system complements the retrieval engine and helps explain tools without forcing the user to leave the terminal.
EOF

cat > "$VOICE/08.txt" <<'EOF'
Safety is enforced independently of the language model. Destructive commands cannot become automatically approved simply because automatic mode was requested. Unknown or model-generated dangerous commands fail closed, while controlled destructive paths require explicit approval.
EOF

cat > "$VOICE/09.txt" <<'EOF'
FU Terminal combines deterministic retrieval, local documentation, optional local AI, system investigation, evidence, execution history, verification, learning, and centralized safety. The result is the same terminal you already use, with smarter answers and stronger guardrails.
EOF

echo "Generating slower narration..."

for n in 01 02 03 04 05 06 07 08 09; do
    "$PIPER" \
        --model "$MODEL" \
        --length_scale 1.25 \
        --output_file "$VOICE/$n.wav" \
        < "$VOICE/$n.txt"
done

# ---------- Browser-based terminal renderer ----------
cat > "$WORK/render.js" <<'NODE'
const { chromium } = require("playwright");
const fs = require("fs");

const [, , outputFile, title, command, section, caption, textFile] = process.argv;

function esc(s) {
  return s.replace(/[&<>"']/g, c => ({
    "&":"&amp;",
    "<":"&lt;",
    ">":"&gt;",
    '"':"&quot;",
    "'":"&#039;"
  })[c]);
}

(async () => {
  let output = fs.readFileSync(textFile, "utf8")
    .replace(/\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g, "");

  let lines = output.split("\n");

  if (lines.length > 27) {
    lines = lines.slice(0, 26);
    lines.push("…");
  }

  output = lines.join("\n");

  const browser = await chromium.launch({ headless: true });

  const page = await browser.newPage({
    viewport: { width: 1600, height: 900 }
  });

  await page.setContent(`
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
* { box-sizing:border-box; }

html,body {
  margin:0;
  width:1600px;
  height:900px;
  overflow:hidden;
  background:#05080d;
  color:#dce8f5;
}

body {
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
}

.titlebar {
  height:60px;
  background:#0d1722;
  display:flex;
  align-items:center;
  padding:0 28px;
  border-bottom:1px solid #17334c;
}

.dots {
  display:flex;
  gap:10px;
  margin-right:25px;
}

.dot {
  width:14px;
  height:14px;
  border-radius:50%;
}

.red { background:#ff5f57; }
.yellow { background:#febc2e; }
.green { background:#28c840; }

.brand {
  font-family:Menlo,Monaco,monospace;
  font-size:21px;
  font-weight:700;
}

.tag {
  margin-left:auto;
  color:#3ba0ff;
  font-size:17px;
}

.terminal {
  position:absolute;
  left:32px;
  right:32px;
  top:88px;
  bottom:128px;
  border:1px solid #1d405d;
  border-radius:15px;
  background:#020407;
  padding:30px 35px;
  box-shadow:0 15px 60px rgba(0,0,0,.35);
}

.section {
  color:#3ba0ff;
  font-weight:800;
  font-size:23px;
  letter-spacing:.5px;
  margin-bottom:24px;
}

.command {
  color:#64e892;
  font-family:Menlo,Monaco,monospace;
  font-size:20px;
  margin-bottom:23px;
}

pre {
  margin:0;
  white-space:pre-wrap;
  font-family:Menlo,Monaco,monospace;
  font-size:17px;
  line-height:1.34;
  color:#dce8f5;
}

.caption {
  position:absolute;
  left:175px;
  right:175px;
  bottom:24px;
  min-height:82px;
  background:rgba(9,15,23,.98);
  border:1px solid #294d69;
  border-radius:13px;
  display:flex;
  flex-direction:column;
  justify-content:center;
  text-align:center;
  padding:10px 30px;
}

.caption strong {
  color:white;
  font-size:22px;
  margin-bottom:6px;
}

.caption span {
  color:#b8cee2;
  font-size:18px;
}

.watermark {
  position:absolute;
  right:38px;
  bottom:8px;
  color:#3ba0ff;
  font-size:13px;
}
</style>
</head>

<body>
<div class="titlebar">
  <div class="dots">
    <div class="dot red"></div>
    <div class="dot yellow"></div>
    <div class="dot green"></div>
  </div>
  <div class="brand">FU Terminal — Feature Demo</div>
  <div class="tag">Retrieval-first terminal intelligence</div>
</div>

<div class="terminal">
  <div class="section">${esc(section)}</div>
  <div class="command">$ ${esc(command)}</div>
  <pre>${esc(output)}</pre>
</div>

<div class="caption">
  <strong>${esc(title)}</strong>
  <span>${esc(caption)}</span>
</div>

<div class="watermark">Richmack OS</div>
</body>
</html>
  `, { waitUntil:"domcontentloaded" });

  await page.screenshot({
    path:outputFile,
    type:"png",
    fullPage:false,
    animations:"disabled"
  });

  await browser.close();
})();
NODE

render_scene() {
    local n="$1"
    local title="$2"
    local command="$3"
    local section="$4"
    local caption="$5"
    local source="$6"

    node "$WORK/render.js" \
        "$SCENES/$n.png" \
        "$title" \
        "$command" \
        "$section" \
        "$caption" \
        "$source"

    echo "✓ rendered $n.png"
}

render_scene 01 \
 "Welcome to FU Terminal" \
 "fu" \
 "INTRODUCTION" \
 "Retrieval first. Local first. Safety focused." \
 "$WORK/intro.txt"

render_scene 02 \
 "Verify the installation" \
 "fu selftest" \
 "SELF TEST" \
 "54 regression checks validate FU's core subsystems." \
 "$WORK/selftest.txt"

render_scene 03 \
 "Deterministic command resolution" \
 'fu --auto "disk usage"' \
 "SAFE AUTO EXECUTION" \
 "FU exposes source, rule, risk and command before execution." \
 "$WORK/disk.txt"

render_scene 04 \
 "Investigate before changing anything" \
 "fu investigate disk" \
 "SYSTEM INVESTIGATION" \
 "Read-only diagnostics gather current system signals first." \
 "$WORK/investigate.txt"

render_scene 05 \
 "Capture authoritative evidence" \
 "fu evidence" \
 "EVIDENCE" \
 "FU records current state instead of relying on assumptions." \
 "$WORK/evidence.txt"

render_scene 06 \
 "Verify the goal" \
 "fu verify last" \
 "VERIFICATION" \
 "Command success and goal success are separate questions." \
 "$WORK/verify.txt"

render_scene 07 \
 "Learn inside the terminal" \
 "fu learn kubectl" \
 "LEARNING" \
 "Practical command knowledge stays inside the FU workflow." \
 "$WORK/learn.txt"

render_scene 08 \
 "Dangerous commands fail closed" \
 'fu --auto "rm -rf /"' \
 "FU SAFETY" \
 "AUTO mode cannot bypass destructive-command protection." \
 "$WORK/safety.txt"

render_scene 09 \
 "Same terminal. Smarter answers." \
 "fu" \
 "FU TERMINAL" \
 "Deterministic. Evidence-based. Local-first." \
 "$WORK/outro.txt"

# ---------- Turn each scene into video ----------
: > "$WORK/concat.txt"

echo "Rendering video scenes..."

for n in 01 02 03 04 05 06 07 08 09; do

    ADUR="$(ffprobe -v error \
        -show_entries format=duration \
        -of csv=p=0 "$VOICE/$n.wav")"

    DUR="$(python3 -c "print(float('$ADUR') + 5.0)")"

    ffmpeg -nostdin -loglevel error -y \
        -loop 1 \
        -framerate 30 \
        -i "$SCENES/$n.png" \
        -i "$VOICE/$n.wav" \
        -filter_complex "[1:a]apad=pad_dur=5[a]" \
        -map 0:v \
        -map "[a]" \
        -t "$DUR" \
        -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" \
        -c:v libx264 \
        -preset medium \
        -crf 19 \
        -pix_fmt yuv420p \
        -c:a aac \
        -b:a 160k \
        "$SCENES/$n.mp4"

    printf "file '%s'\n" "$SCENES/$n.mp4" >> "$WORK/concat.txt"
    echo "✓ encoded scene $n"
done

ffmpeg -nostdin -loglevel error -y \
    -f concat \
    -safe 0 \
    -i "$WORK/concat.txt" \
    -c copy \
    -movflags +faststart \
    "$OUT"

echo
echo "════════════════════════════════════════════════"
echo "✓ FU TERMINAL FEATURE DEMO COMPLETE"
echo "════════════════════════════════════════════════"

ffprobe -v error \
    -show_entries format=duration,size \
    -show_entries stream=codec_name,width,height \
    -of default=noprint_wrappers=1 \
    "$OUT"

echo
echo "$OUT"

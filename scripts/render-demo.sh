#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
./scripts/render-screenshots.sh
mkdir -p media demo/.voice
VOICE_DIR="$HOME/.local/share/fu-terminal/voices/en_US-ryan-high"
MODEL="$VOICE_DIR/en_US-ryan-high.onnx"; JSON="$MODEL.json"
if ! command -v piper >/dev/null 2>&1; then
  python3 -m venv demo/.venv; demo/.venv/bin/pip install -q piper-tts; PIPER=demo/.venv/bin/piper
else PIPER=piper; fi
mkdir -p "$VOICE_DIR"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high"
[ -f "$MODEL" ] || curl -L --fail -o "$MODEL" "$BASE/en_US-ryan-high.onnx"
[ -f "$JSON" ] || curl -L --fail -o "$JSON" "$BASE/en_US-ryan-high.onnx.json"
"$PIPER" --model "$MODEL" --output_file demo/.voice/narration.wav < demo/narration.txt
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 demo/.voice/narration.wav)
ffmpeg -y -loop 1 -t "$DUR" -i media/investigate-disk.png -i demo/.voice/narration.wav -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest media/fu-terminal-feature-demo.mp4
printf 'Created %s\n' "$ROOT/media/fu-terminal-feature-demo.mp4"

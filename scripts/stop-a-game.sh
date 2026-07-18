#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT/.a-game-runtime.pid"
if [ -f "$PID_FILE" ]; then
  PID="$(tr -dc '0-9' < "$PID_FILE")"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then kill "$PID"; fi
  rm -f "$PID_FILE"
fi
pkill -f "$ROOT/.tools/Blenderplayer.app/Contents/MacOS/Blenderplayer all_game.blend" 2>/dev/null || true

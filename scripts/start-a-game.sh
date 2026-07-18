#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLAYER="$ROOT/.tools/Blenderplayer.app/Contents/MacOS/Blenderplayer"
PORT=3218

if [ ! -x "$PLAYER" ]; then
  echo "UPBGE 0.36.1 is missing at: $PLAYER"
  echo "Run the local setup or install the macOS x86_64 UPBGE 0.36.1 player, then retry."
  exit 1
fi

if curl --connect-timeout 1 -fsS "http://127.0.0.1:$PORT/api/state" >/dev/null 2>&1; then
  echo "Anjali simulation is already running."
else
  "$PLAYER" "$ROOT/all_game.blend" >"$ROOT/.a-game-runtime.log" 2>&1 &
  echo $! > "$ROOT/.a-game-runtime.pid"
  for _ in $(seq 1 90); do
    if curl --connect-timeout 1 -fsS "http://127.0.0.1:$PORT/api/state" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
if [ -z "$LAN_IP" ]; then LAN_IP="127.0.0.1"; fi
echo "Local: http://127.0.0.1:$PORT/"
echo "Wi-Fi: http://$LAN_IP:$PORT/"

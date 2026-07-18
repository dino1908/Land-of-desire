import json
import mimetypes
import os
import queue
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import bge
import bpy

ROOT = Path(bge.logic.expandPath("//"))
WEB_ROOT = ROOT / "web"
FRAME_PATH = ROOT / "Data" / "web_frame.png"
PENDING_FRAME_PATH = ROOT / "Data" / "web_frame.pending.png"
COMMANDS = queue.Queue()
STATE_LOCK = threading.Lock()
STATE = {
    "ready": False,
    "character": "Anjali",
    "scene": "Delhi flat",
    "pose": "",
    "speed": 1.0,
    "poses": [],
    "prompt": "Loading Anjali and the simulation…",
    "runtime": {},
}
SERVER_STARTED = False
LAST_CAPTURE = 0.0
ROLEPLAY = {}


def _json_bytes(payload):
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            with STATE_LOCK:
                payload = dict(STATE)
            self._send(200, _json_bytes(payload), "application/json; charset=utf-8")
            return
        if path == "/frame.png":
            if FRAME_PATH.exists():
                self._send(200, FRAME_PATH.read_bytes(), "image/png")
            else:
                self._send(404, b"frame not ready", "text/plain; charset=utf-8")
            return
        requested = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (WEB_ROOT / requested).resolve()
        if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
            self._send(403, b"forbidden", "text/plain")
            return
        if not target.is_file():
            self._send(404, b"not found", "text/plain")
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self._send(200, target.read_bytes(), content_type)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send(400, _json_bytes({"ok": False, "error": "invalid json"}), "application/json")
            return
        path = urlparse(self.path).path
        if path == "/api/pose":
            COMMANDS.put(("pose", str(payload.get("pose", ""))))
        elif path == "/api/speed":
            COMMANDS.put(("speed", float(payload.get("speed", 1.0))))
        elif path == "/api/phase":
            COMMANDS.put(("phase", str(payload.get("phase", "slow"))))
        else:
            self._send(404, _json_bytes({"ok": False}), "application/json")
            return
        self._send(200, _json_bytes({"ok": True}), "application/json")


def _start_server():
    global SERVER_STARTED
    if SERVER_STARTED:
        return
    server = ThreadingHTTPServer(("0.0.0.0", 3218), Handler)
    threading.Thread(target=server.serve_forever, name="anjali-web-bridge", daemon=True).start()
    SERVER_STARTED = True
    print("[ANJALI] Web bridge listening on 0.0.0.0:3218")


def _normal(name):
    return re.sub(r"\.\d+$", "", name)


def _pose_map():
    man = bpy.data.objects.get("man")
    woman = bpy.data.objects.get("woman")
    if not man or not woman or not man.animation_data or not woman.animation_data:
        return {}
    men = {_normal(track.name): track.name for track in man.animation_data.nla_tracks}
    women = {_normal(track.name): track.name for track in woman.animation_data.nla_tracks}
    return {name: (men[name], women[name]) for name in sorted(set(men) & set(women))}


def _direction(phase):
    cards = ROLEPLAY.get("scene_cards", {})
    return cards.get(phase, cards.get("slow", "Hold Anjali in character and leave Roshan's next response open."))


def _apply_pose(label):
    mapping = _pose_map()
    if label not in mapping:
        return
    male_pose, female_pose = mapping[label]
    scene = bge.logic.getCurrentScene()
    holder = scene.objects.get("game_scene_script_holder")
    if not holder:
        return
    holder["male_pose"] = male_pose
    holder["female_pose"] = female_pose
    holder["anim_frame"] = 0.0
    ends = []
    for action_name in (male_pose, female_pose):
        action = bpy.data.actions.get(action_name)
        if action:
            ends.append(action.frame_range[1])
    holder["pose_last_frame"] = max(ends) if ends else 100.0
    with STATE_LOCK:
        STATE["pose"] = label
        STATE["prompt"] = _direction("slow")
    prompt_obj = scene.objects.get("anjali_roleplay_prompt")
    if prompt_obj:
        prompt_obj["Text"] = f"POSE: {label}\n{_direction('slow')}"


def _consume_commands():
    scene = bge.logic.getCurrentScene()
    holder = scene.objects.get("game_scene_script_holder")
    while True:
        try:
            kind, value = COMMANDS.get_nowait()
        except queue.Empty:
            break
        if kind == "pose":
            _apply_pose(value)
        elif kind == "speed" and holder:
            speed = max(0.1, min(float(value), 3.0))
            holder["animation_speed"] = speed
            with STATE_LOCK:
                STATE["speed"] = speed
        elif kind == "phase":
            with STATE_LOCK:
                STATE["prompt"] = _direction(value)
            prompt_obj = scene.objects.get("anjali_roleplay_prompt")
            if prompt_obj:
                prompt_obj["Text"] = f"{value.upper()}\n{_direction(value)}"


def tick():
    global LAST_CAPTURE, ROLEPLAY
    _start_server()
    if not ROLEPLAY:
        try:
            ROLEPLAY = json.loads((ROOT / "Data" / "anjali_roleplay.json").read_text())
        except Exception:
            ROLEPLAY = {"scene_cards": {}}
    mapping = _pose_map()
    scene = bge.logic.getCurrentScene()
    holder = scene.objects.get("game_scene_script_holder")
    character_holder = scene.objects.get("characters_holder")
    runtime = {
        "scene": scene.name,
        "already_loaded": bool(holder and holder.get("already_loaded", False)),
        "female_file": str(holder.get("female_char", "")) if holder else "",
        "male_file": str(holder.get("male_char", "")) if holder else "",
        "scene_file": str(holder.get("scene_to_load", "")) if holder else "",
        "armatures": str(holder.get("Armatures", "")) if holder else "",
        "character_children": len(character_holder.children) if character_holder else -1,
        "has_female_body": scene.objects.get("female_1") is not None,
        "has_male_body": scene.objects.get("man_1") is not None,
    }
    with STATE_LOCK:
        STATE["poses"] = list(mapping)
        STATE["ready"] = bool(mapping) and runtime["has_female_body"] and runtime["has_male_body"]
        STATE["runtime"] = runtime
        if mapping and not STATE["pose"]:
            STATE["prompt"] = _direction("setup")
    _consume_commands()
    now = time.monotonic()
    if now - LAST_CAPTURE >= 0.18:
        try:
            bge.render.makeScreenshot(str(PENDING_FRAME_PATH))
            frame_bytes = PENDING_FRAME_PATH.read_bytes()
            if frame_bytes.startswith(b"\x89PNG\r\n\x1a\n") and frame_bytes.endswith(b"IEND\xaeB`\x82"):
                os.replace(PENDING_FRAME_PATH, FRAME_PATH)
                LAST_CAPTURE = now
        except Exception as exc:
            with STATE_LOCK:
                STATE["prompt"] = f"Renderer active; frame bridge waiting: {exc}"

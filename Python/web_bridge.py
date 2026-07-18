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
from mathutils import Vector

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
    "phase": "slow",
    "poses": [],
    "prompt": "Loading Anjali and the simulation…",
    "runtime": {},
}
SERVER_STARTED = False
LAST_CAPTURE = 0.0
LAST_CAPTURE_REQUEST = 0.0
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
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            with STATE_LOCK:
                payload = dict(STATE)
            self._send(200, _json_bytes(payload), "application/json; charset=utf-8")
            return
        if path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            last_modified = 0
            try:
                while True:
                    if FRAME_PATH.exists():
                        modified = FRAME_PATH.stat().st_mtime_ns
                        if modified != last_modified:
                            frame = FRAME_PATH.read_bytes()
                            if frame.startswith(b"\x89PNG\r\n\x1a\n") and frame.endswith(b"IEND\xaeB`\x82"):
                                self.wfile.write(b"--frame\r\nContent-Type: image/png\r\n")
                                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                                self.wfile.write(frame)
                                self.wfile.write(b"\r\n")
                                self.wfile.flush()
                                last_modified = modified
                    time.sleep(0.025)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
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


PHASE_SPEEDS = {
    "setup": 0.35,
    "care": 0.45,
    "tease": 0.65,
    "slow": 1.0,
    "fast": 1.8,
    "finish": 2.4,
    "aftercare": 0.3,
}


def _hide_native_hud(scene):
    # The fixed-size native HUD covers most of a 16:9 remote capture. The
    # browser supplies equivalent controls, so expose the full 3D stage.
    names = (
        "pose_lists_background", "pose_lists_holder", "arousal_bars_background",
        "male_shirt_button", "male_pants_button", "male_shoes_button",
        "female_shirt_button", "female_pants_button", "female_shoes_button",
        "load_screen", "current_load_state_text", "Text.016",
    )
    for name in names:
        obj = scene.objects.get(name)
        if obj and obj.visible:
            obj.setVisible(False, True)


def _position_and_frame_stage(scene, pose_label):
    character_holder = scene.objects.get("characters_holder")
    camera = scene.active_camera
    if not character_holder or not camera:
        return
    area = pose_label.split(":", 1)[1] if ":" in pose_label else "bed/floor"
    marker = scene.objects.get(f"{area}_marker")
    if marker:
        character_holder.worldPosition = marker.worldPosition.copy()
        character_holder.worldOrientation = marker.worldOrientation.copy()
    target_heights = {"chair": 0.3, "table": 0.28, "bed/floor": 0.28}
    camera_offsets = {
        "chair": Vector((0.9, -1.9, 1.4)),
        "table": Vector((1.2, 1.5, 1.2)),
        "bed/floor": Vector((1.1, -2.2, 1.35)),
    }
    height = target_heights.get(area, 0.28)
    offset = camera_offsets.get(area, camera_offsets["bed/floor"])
    camera.worldPosition = character_holder.worldPosition + (character_holder.worldOrientation @ offset)
    target = character_holder.worldPosition + (character_holder.worldOrientation @ Vector((0.0, 0.0, height)))
    direction = target - camera.worldPosition
    if direction.length > 0.001:
        camera.worldOrientation = direction.to_track_quat("-Z", "Y").to_matrix()


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
    _position_and_frame_stage(scene, label)
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
            phase = value if value in PHASE_SPEEDS else "slow"
            if holder:
                holder["animation_speed"] = PHASE_SPEEDS[phase]
            with STATE_LOCK:
                STATE["phase"] = phase
                STATE["speed"] = PHASE_SPEEDS[phase]
                STATE["prompt"] = _direction(phase)
            prompt_obj = scene.objects.get("anjali_roleplay_prompt")
            if prompt_obj:
                prompt_obj["Text"] = f"{phase.upper()}\n{_direction(phase)}"


def tick():
    global LAST_CAPTURE, LAST_CAPTURE_REQUEST, ROLEPLAY
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
    if holder and holder.get("already_loaded", False):
        _hide_native_hud(scene)
    animation_frames = {}
    if holder:
        for name in [n for n in holder.get("Armatures", "").split("|") if n]:
            armature = scene.objects.get(name)
            if armature and armature.isPlayingAction(1):
                animation_frames[name] = round(float(armature.getActionFrame(1)), 3)
    camera = scene.active_camera
    female_body = scene.objects.get("female_1")
    male_body = scene.objects.get("man_1")

    def position(obj):
        return [round(float(v), 3) for v in obj.worldPosition] if obj else None

    def screen_position(obj):
        if not camera or not obj:
            return None
        try:
            return [round(float(v), 3) for v in camera.getScreenPosition(obj)]
        except Exception:
            return None

    runtime = {
        "scene": scene.name,
        "already_loaded": bool(holder and holder.get("already_loaded", False)),
        "female_file": str(holder.get("female_char", "")) if holder else "",
        "male_file": str(holder.get("male_char", "")) if holder else "",
        "scene_file": str(holder.get("scene_to_load", "")) if holder else "",
        "armatures": str(holder.get("Armatures", "")) if holder else "",
        "character_children": len(character_holder.children) if character_holder else -1,
        "has_female_body": female_body is not None,
        "has_male_body": male_body is not None,
        "animation_frames": animation_frames,
        "area": str(holder.get("area", "")) if holder else "",
        "characters_position": position(character_holder),
        "female_position": position(female_body),
        "male_position": position(male_body),
        "camera": camera.name if camera else None,
        "camera_position": position(camera),
        "female_screen": screen_position(female_body),
        "male_screen": screen_position(male_body),
        "hud_visible": {
            name: bool(scene.objects[name].visible)
            for name in ("pose_lists_background", "load_screen")
            if name in scene.objects
        },
    }
    with STATE_LOCK:
        STATE["poses"] = list(mapping)
        STATE["ready"] = bool(mapping) and runtime["has_female_body"] and runtime["has_male_body"]
        STATE["runtime"] = runtime
        if mapping and not STATE["pose"]:
            STATE["prompt"] = _direction("setup")
    _consume_commands()
    if mapping and not STATE["pose"] and runtime["has_female_body"] and runtime["has_male_body"]:
        default_pose = "missionary:bed/floor" if "missionary:bed/floor" in mapping else next(iter(mapping))
        _apply_pose(default_pose)
    elif STATE["pose"]:
        _position_and_frame_stage(scene, STATE["pose"])
    now = time.monotonic()
    try:
        if PENDING_FRAME_PATH.exists():
            frame_bytes = PENDING_FRAME_PATH.read_bytes()
            if frame_bytes.startswith(b"\x89PNG\r\n\x1a\n") and frame_bytes.endswith(b"IEND\xaeB`\x82"):
                os.replace(PENDING_FRAME_PATH, FRAME_PATH)
                LAST_CAPTURE = now
        if not PENDING_FRAME_PATH.exists() and now - LAST_CAPTURE_REQUEST >= 0.08:
            bge.render.makeScreenshot(str(PENDING_FRAME_PATH))
            LAST_CAPTURE_REQUEST = now
    except Exception as exc:
        with STATE_LOCK:
            STATE["prompt"] = f"Renderer active; frame bridge waiting: {exc}"

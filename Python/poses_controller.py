import bge
import bpy
import os
import sys


ANIMATION_LAYER = 1


def _action_range(action_name, fallback_end):
    action = bpy.data.actions.get(action_name)
    if action:
        return float(action.frame_range[0]), float(action.frame_range[1])
    return 0.0, max(float(fallback_end), 1.0)


def update_armatures_animation():
    scene = bge.logic.getCurrentScene()
    holder = scene.objects.get("game_scene_script_holder")
    if not holder:
        print("[ERROR] No se encontró game_scene_script_holder")
        return

    armature_names = [n.strip() for n in holder.get("Armatures", "").split("|") if n.strip()]
    speed = max(float(holder.get("animation_speed", 1.0)), 0.05)
    fallback_end = max(float(holder.get("pose_last_frame", 1.0)), 1.0)
    male_pose = holder.get("male_pose", "")
    female_pose = holder.get("female_pose", "")
    frames = []

    for name in armature_names:
        armature = scene.objects.get(name)
        if not armature or not hasattr(armature, "playAction"):
            continue

        lower_name = name.lower()
        if "female" in lower_name or "woman" in lower_name:
            action_name = female_pose
        elif "male" in lower_name or "man" in lower_name:
            action_name = male_pose
        else:
            continue
        if not action_name:
            continue

        start_frame, end_frame = _action_range(action_name, fallback_end)
        current_action = armature.getActionName(ANIMATION_LAYER)
        previous_speed = float(armature.get("anjali_action_speed", -1.0))
        needs_restart = (
            current_action != action_name
            or not armature.isPlayingAction(ANIMATION_LAYER)
            or abs(previous_speed - speed) > 0.0001
        )
        if needs_restart:
            resume_frame = start_frame
            if current_action == action_name:
                try:
                    resume_frame = armature.getActionFrame(ANIMATION_LAYER)
                except Exception:
                    pass
            armature.stopAction(ANIMATION_LAYER)
            armature.playAction(
                action_name,
                start_frame,
                end_frame,
                play_mode=bge.logic.KX_ACTION_MODE_LOOP,
                speed=speed,
                layer=ANIMATION_LAYER,
                blendin=5,
            )
            if start_frame <= resume_frame <= end_frame:
                armature.setActionFrame(resume_frame, ANIMATION_LAYER)
            armature["anjali_action_speed"] = speed

        try:
            frames.append(float(armature.getActionFrame(ANIMATION_LAYER)))
        except Exception:
            pass

    if frames:
        holder["anim_frame"] = sum(frames) / len(frames)


# Direct-start mode bypasses the selector's startup message. Execute the
# original loader once from this always-on controller before animating.
_scene = bge.logic.getCurrentScene()
_holder = _scene.objects.get("game_scene_script_holder")
if _holder and not _holder.get("already_loaded", False):
    _loader_path = os.path.join(bge.logic.expandPath("//"), "Python", "game_scene_start.py")
    with open(_loader_path, "r", encoding="utf-8") as _loader_file:
        exec(compile(_loader_file.read(), _loader_path, "exec"), globals(), globals())

update_armatures_animation()

# The existing pose controller runs every frame, making it the stable hook
# for the browser bridge without adding fragile logic bricks to the blend.
python_dir = os.path.join(bge.logic.expandPath("//"), "Python")
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)
try:
    import web_bridge
    web_bridge.tick()
except Exception as exc:
    print(f"[ANJALI] Web bridge tick failed: {exc}")

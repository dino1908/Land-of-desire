import bge
import os
import sys


def update_armatures_animation():
    scene = bge.logic.getCurrentScene()
    holder = scene.objects.get("game_scene_script_holder")
    if not holder:
        print("[ERROR] No se encontró game_scene_script_holder")
        return

    armature_names = [n.strip() for n in holder.get("Armatures", "").split("|") if n.strip()]
    anim_speed  = holder["animation_speed"]
    anim_frame  = holder["anim_frame"]
    last_frame  = holder["pose_last_frame"]

    male_pose   = holder.get("male_pose", "")
    female_pose = holder.get("female_pose", "")

    for name in armature_names:
        kx_arm = scene.objects.get(name)
        if not kx_arm or not hasattr(kx_arm, 'playAction'):
#            print(f"[ADVERTENCIA] No se encontró armature: {name}")
            continue

        lname = name.lower()
        if "female" in lname or "woman" in lname:
            action_name = female_pose
        elif "male" in lname or "man" in lname:
            action_name = male_pose
        else:
#            print(f"[ADVERTENCIA] Género no detectado en: {name}")
            continue

        if not action_name:
#            print(f"[ERROR] Pose no definida para {name}")
            continue

        kx_arm.playAction(action_name, anim_frame, anim_frame, bge.logic.KX_ACTION_MODE_PLAY, 1)

    # Asignar correctamente el nuevo frame
    anim_frame = anim_frame + anim_speed
    
    if anim_frame > last_frame:
        anim_frame = 0
        
    holder["anim_frame"] = anim_frame  # <--- CORRECTO

 #   print("Frame actual:", anim_frame, " frame final:",last_frame)




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

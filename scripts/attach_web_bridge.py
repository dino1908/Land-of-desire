from pathlib import Path
import bpy

root = Path(bpy.path.abspath("//"))
scene = bpy.data.scenes["game_scene"]
bpy.context.window.scene = scene
holder = scene.objects["game_scene_script_holder"]


def set_game_property(name, value):
    prop = holder.game.properties.get(name)
    if prop is None:
        raise KeyError(f"Missing UPBGE game property: {name}")
    prop.value = value


set_game_property("female_char", "Anjali.json")
set_game_property("male_char", "Victor.json")
set_game_property("scene_to_load", "Home bedroom.blend")
set_game_property("already_loaded", False)
set_game_property("animation_speed", 1.0)
set_game_property("anim_frame", 0.0)
set_game_property("pose_last_frame", 100.0)

# Starting directly in game_scene bypasses the selector's Message sensor.
# Link its existing startup controller to the already-present Always sensor;
# game_scene_start.py remains one-shot because it sets already_loaded=True.
startup_controller = holder.game.controllers.get("Python")
always_sensor = holder.game.sensors.get("Always")
if startup_controller and always_sensor:
    always_sensor.link(startup_controller)

for text_name, relative_path in (
    ("poses_controller.py", "Python/poses_controller.py"),
    ("game_scene_pose_button_clic.py", "Python/game_scene_pose_button_clic.py"),
):
    text = bpy.data.texts.get(text_name)
    path = root / relative_path
    if text and path.exists():
        text.clear()
        text.write(path.read_text())
        text.filepath = f"//{relative_path}"

bpy.ops.wm.save_as_mainfile(filepath=str(root / "all_game.blend"))
print("Anjali web bridge embedded through poses_controller; game_scene set as startup")

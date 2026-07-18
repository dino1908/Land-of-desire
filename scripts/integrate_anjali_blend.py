from pathlib import Path
import bpy

root = Path(bpy.path.abspath("//"))
game_scene = bpy.data.scenes["game_scene"]
menu_collection = bpy.data.collections["game_scene_menues"]
pose_holder = game_scene.objects["pose_lists_holder"]
font_template = game_scene.objects["poses_buttons_template_Text"]


def add_card_text(name, body, location, scale, line_spacing=1.0):
    existing = bpy.data.objects.get(name)
    if existing:
        for collection in list(existing.users_collection):
            collection.objects.unlink(existing)
        bpy.data.objects.remove(existing, do_unlink=True)
    curve = font_template.data.copy()
    curve.name = f"{name}_font"
    curve.body = body
    curve.align_x = "LEFT"
    curve.align_y = "TOP_BASELINE"
    curve.space_line = line_spacing
    curve.size = 1.0
    obj = bpy.data.objects.new(name, curve)
    menu_collection.objects.link(obj)
    obj.location = location
    obj.scale = (scale, scale, scale)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj["Text"] = body
    return obj


add_card_text(
    "anjali_roleplay_title",
    "ANJALI  /  TRIO FULL",
    (12.05, 2.55, 0.055),
    0.095,
)
add_card_text(
    "anjali_roleplay_prompt",
    "DELHI FLAT  •  SIMULATION READY\nSelect a pose. Hold the physical beat; let Anjali's shy, duty-led conflict move the scene.\nHer action ends on an open hook. Roshan's next response remains yours.",
    (12.05, 2.20, 0.052),
    0.045,
    1.25,
)
add_card_text(
    "anjali_roleplay_rule",
    "AGENCY LOCK\nThe simulation never invents Roshan's dialogue, movement, gaze, feelings or consent.",
    (12.05, 1.30, 0.052),
    0.043,
    1.20,
)

# Default Anjali in the selector while retaining the normal character list.
selector_holder = bpy.data.scenes["character_selector"].objects.get("character_selector_script_holder")
if selector_holder:
    selector_holder["female_char"] = "Anjali.json"
    if not selector_holder.get("male_char", ""):
        selector_holder["male_char"] = "Victor.json"

# Add a visible title treatment to the main menu.
main_scene = bpy.data.scenes["Main_menu"]
main_collection = next(iter(main_scene.objects["Text.002"].users_collection))
main_existing = bpy.data.objects.get("anjali_main_menu_subtitle")
if main_existing:
    bpy.data.objects.remove(main_existing, do_unlink=True)
main_curve = main_scene.objects["Text.002"].data.copy()
main_curve.body = "ANJALI  •  TRIO FULL EDITION"
main_obj = bpy.data.objects.new("anjali_main_menu_subtitle", main_curve)
main_collection.objects.link(main_obj)
main_obj.location = (-6.22, 3.15, 0.006)
main_obj.scale = (0.62, 0.62, 0.62)
main_obj["Text"] = main_curve.body

# The blend stores script text internally. Reload the patched external script.
text_block = bpy.data.texts.get("game_scene_pose_button_clic.py")
script_path = root / "Python/game_scene_pose_button_clic.py"
if text_block and script_path.exists():
    text_block.clear()
    text_block.write(script_path.read_text())
    text_block.filepath = "//Python/game_scene_pose_button_clic.py"

bpy.ops.wm.save_as_mainfile(filepath=str(root / "all_game.blend"))
print("Anjali UI and roleplay integration saved to all_game.blend")

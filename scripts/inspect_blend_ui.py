import bpy

for scene_name in ("Main_menu", "character_selector", "game_scene"):
    scene = bpy.data.scenes[scene_name]
    print(f"\n=== {scene_name} ===")
    print("camera", scene.camera.name if scene.camera else None)
    for obj in sorted(scene.objects, key=lambda item: item.name.lower()):
        if obj.type in {"FONT", "CAMERA", "EMPTY"} or "holder" in obj.name.lower() or "button" in obj.name.lower():
            text = obj.data.body[:120].replace("\n", "\\n") if obj.type == "FONT" else ""
            props = {key: obj[key] for key in obj.keys() if key != "_RNA_UI"}
            print(obj.name, obj.type, tuple(round(v, 3) for v in obj.location), text, props)

import bpy
import bge
import json
import os

cont = bge.logic.getCurrentController()
owner = cont.owner
mouse_clic = cont.sensors["MouseClick"]
mouse_over = cont.sensors["MouseOver"]
script_holder = bge.logic.getCurrentScene().objects["game_scene_script_holder"]

if mouse_clic.positive and mouse_over.positive:
    # Valores de pose seleccionados
    male_pose = owner.get("pose_name_male", "")
    female_pose = owner.get("pose_name_female", "")

    script_holder["male_pose"] = male_pose
    script_holder["female_pose"] = female_pose

    # Determinar qué action usar para man/woman, incluso si están vacíos
    def get_action_end(arm_obj_name, pose_prop):
        arm_obj = bpy.data.objects.get(arm_obj_name)
        if arm_obj is None or arm_obj.type != 'ARMATURE':
            return 0
        action_name = script_holder.get(pose_prop) or arm_obj.animation_data and arm_obj.animation_data.action and arm_obj.animation_data.action.name
        if not action_name:
            return 0
        action = bpy.data.actions.get(action_name)
        if not action:
            return 0
        return action.frame_range[1]  # frame_range es un Vector [start,end] :contentReference[oaicite:1]{index=1}

    end_man = get_action_end("man", "male_pose")
    end_woman = get_action_end("woman", "female_pose")
    last_frame = max(end_man, end_woman)
    script_holder["pose_last_frame"] = last_frame
    print("pose_last_frame establecido a", last_frame)

    # Update the Anjali / Trio Full roleplay steering card for the selected
    # physical simulation. This stays deterministic and never narrates Roshan.
    prompt_obj = bge.logic.getCurrentScene().objects.get("anjali_roleplay_prompt")
    if prompt_obj:
        pose_label = (female_pose or male_pose or "selected pose").lower()
        roleplay_path = os.path.join(bge.logic.expandPath("//"), "Data", "anjali_roleplay.json")
        try:
            with open(roleplay_path, "r", encoding="utf-8") as roleplay_file:
                roleplay = json.load(roleplay_file)
            cards = roleplay.get("scene_cards", {})
            if any(token in pose_label for token in ("idle", "stand", "start", "intro")):
                phase = "setup"
            elif any(token in pose_label for token in ("kiss", "touch", "tease")):
                phase = "tease"
            elif any(token in pose_label for token in ("fast", "hard")):
                phase = "fast"
            elif any(token in pose_label for token in ("finish", "orgasm", "cum")):
                phase = "finish"
            else:
                phase = "slow"
            direction = cards.get(phase, cards.get("slow", "Keep Anjali in character and leave Roshan's response open."))
            prompt_obj["Text"] = f"POSE: {female_pose or male_pose}\n{direction}"
        except Exception as exc:
            prompt_obj["Text"] = f"POSE: {female_pose or male_pose}\nAnjali stays shy, duty-led and responsive. Roshan's next action remains open."
            print(f"[WARN] Could not load Anjali roleplay card: {exc}")



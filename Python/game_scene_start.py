import json
import os
import bpy
import bge
import math
from mathutils import Matrix
from bge import logic


this_scene = bge.logic.getCurrentScene()
loading_text = this_scene.objects["current_load_state_text"]
loading_text["Text"] = "Starting load"


# -------------------- FUNCIONES AUXILIARES --------------------

def apply_hsv_to_materials(base_obj_name, keyword, channel, value):
    loading_text["Text"] = "Applying hsv to materials"
    obj = bpy.data.objects.get(base_obj_name)
    if not obj:
        print(f"[ERROR] Objeto base '{base_obj_name}' no encontrado.")
        return

    channel_index = {"hue": 0, "saturation": 1, "value": 2}
    index = channel_index.get(channel)
    if index is None:
        print(f"[ERROR] Canal HSV inválido: {channel}")
        return

    def process_object(o):
        for slot in o.material_slots:
            mat = slot.material
            if mat and keyword.lower() in mat.name.lower():
                if mat.use_nodes:
                    hsv_node = next((n for n in mat.node_tree.nodes if n.type == 'HUE_SAT'), None)
                    if hsv_node:
                        hsv_node.inputs[index].default_value = value
                        print(f"[OK] {channel}={value} aplicado a '{mat.name}' en '{o.name}'")
                    else:
                        print(f"[WARN] Nodo HSV no encontrado en '{mat.name}'")
                else:
                    print(f"[WARN] Material '{mat.name}' no usa nodos")
    process_object(obj)
    for child in obj.children:
        process_object(child)


def load_blend_objects(full_path):
    loading_text["Text"] = "Loading .blend files"
    if not os.path.exists(full_path):
        print(f"[ADVERTENCIA] No se encontró el archivo {full_path}")
        return []

    try:
        with bpy.data.libraries.load(full_path, link=False) as (data_from, data_to):
            data_to.objects = data_from.objects

        imported = []
        for obj in data_to.objects:
            if obj is None:
                continue
            if obj.name not in bpy.context.scene.objects:
                bpy.context.scene.collection.objects.link(obj)
                imported.append(obj)
        return imported

    except Exception as e:
        print(f"[ERROR] Falló al cargar {full_path}: {e}")
        return []


def rename_object(obj, prefix):
    new_name = f"{prefix}_{obj.name}"
    counter = 1
    while new_name in bpy.data.objects:
        new_name = f"{prefix}_{obj.name}_{counter:03d}"
        counter += 1
    obj.name = new_name
    return obj.name


def copy_shape_keys(source_body, target_obj):
    loading_text["Text"] = "Copying shape keys"
    if target_obj.type != 'MESH':
        return
    if not (target_obj.data.shape_keys and source_body and source_body.data.shape_keys):
        return
    for sk_name, sk_block in target_obj.data.shape_keys.key_blocks.items():
        if sk_name in source_body.data.shape_keys.key_blocks:
            sk_block.value = source_body.data.shape_keys.key_blocks[sk_name].value






def register_armature(obj, script_holder, prefix="Base_Mesh_"):
    loading_text["Text"] = "Registering armatures"
    """
    Renombra el armature y lo registra en la propiedad 'Armatures' de 'game_scene_script_holder'
    """
    if obj.type != 'ARMATURE' or not script_holder:
        return

    # Renombrar armature
    new_name = prefix + obj.name
    counter = 1
    while new_name in bpy.data.objects:
        new_name = f"{prefix}{obj.name}_{counter:03d}"
        counter += 1
    obj.name = new_name

    # Añadirlo a la propiedad 'Armatures'
    current_value = script_holder.get("Armatures", "")
    if current_value:
        script_holder["Armatures"] = current_value + "|" + obj.name
    else:
        script_holder["Armatures"] = obj.name
    print(f"[INFO] Armature {obj.name} registrado en 'Armatures'.")






def convert_and_parent(objs, scene, parent_name):
    loading_text["Text"] = "Convertig and parenting"
    parent = scene.objects.get(parent_name)
    if not parent:
        print(f"[ADVERTENCIA] '{parent_name}' no encontrado en la escena.")
        return
    for obj in objs:
        try:
            kx_obj = scene.convertBlenderObject(obj)
            kx_obj.setParent(parent)
            kx_obj.position = (0, 0, 0)
        except Exception as e:
            print(f"[ERROR] No se pudo convertir '{obj.name}': {e}")


# -------------------- FUNCIONES DE CARGA --------------------

def load_template_and_apply_json(json_path, gender, root_name):
    loading_text["Text"] = "Loading templates"
    """
    Para .json: carga la plantilla base, luego aplica shape keys y materiales según el .json
    """
    scene = logic.getCurrentScene()
    objects = scene.objects

  
    # -------------------- CARGAR PLANTILLA BASE --------------------
    template_file = "Female_char_template.blend" if gender.lower() == "female" else "Male_char_template.blend"
    template_path = os.path.join(bge.logic.expandPath("//"), "Characters", template_file)
    template_objs = load_blend_objects(template_path)

    if not template_objs:
        print(f"[ERROR] No se pudo cargar la plantilla base {template_file}")
        return

    game_script_holder = logic.getCurrentScene().objects.get("game_scene_script_holder")

    # Renombrar y registrar cualquier armature importado del template
    for obj in template_objs:
        register_armature(obj, game_script_holder)

    convert_and_parent(template_objs, scene, "characters_holder")

    kx_body = objects.get(root_name)
    body = bpy.data.objects.get(root_name)  # ← Añadido para tener acceso a datos de bpy

    # -------------------- LEER JSON --------------------
    if not os.path.exists(json_path):
        print(f"[ERROR] No se encontró el JSON {json_path}")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)

    # Shape keys
    if body and body.data.shape_keys:
        for key_name, value in data.get("shape_keys", {}).items():
            if key_name in body.data.shape_keys.key_blocks:
                body.data.shape_keys.key_blocks[key_name].value = value

    # Propiedades KX_GameObject
    for prop_name, value in data.get("properties", {}).items():
        if kx_body:
            kx_body[prop_name] = value

    # -------------------- CARGAR PARTES --------------------
    base_dirs = {
        "male": os.path.join(bge.logic.expandPath("//"), "Characters", "Male"),
        "female": os.path.join(bge.logic.expandPath("//"), "Characters", "Female")
    }

    folder_map = {
        "hair": "Hairs",
        "pants": "Clothes/Pants",
        "shoes": "Clothes/Shoes",
        "torso_up": "Clothes/Torso"
    }

    game_script_holder = objects.get("game_scene_script_holder")

    for part, blend_file in data.get("blend_files", {}).items():
        if not blend_file:
            continue
        subdir = folder_map.get(part)
        if not subdir:
            print(f"[ADVERTENCIA] Parte desconocida: {part}")
            continue
        full_path = os.path.join(base_dirs[gender], subdir, blend_file)
        imported_objs = load_blend_objects(full_path)

        for obj in imported_objs:
            rename_object(obj, f"{gender}_{part}")
            copy_shape_keys(body, obj)
            register_armature(obj, game_script_holder)

        convert_and_parent(imported_objs, scene, "characters_holder")

    # -------------------- APLICAR HSV --------------------
    if kx_body:
        props = data.get("properties", {})
        for prop in ["skin_hue", "skin_sat", "skin_val",
                     "iris_hue", "iris_sat", "iris_val",
                     "brow_hue", "brow_sat", "brow_val"]:
            if prop in props:
                kx_body[prop] = props[prop]

        apply_hsv_to_materials(root_name, "skin", "hue", props.get("skin_hue", 0))
        apply_hsv_to_materials(root_name, "skin", "saturation", props.get("skin_sat", 0))
        apply_hsv_to_materials(root_name, "skin", "value", props.get("skin_val", 0))

        apply_hsv_to_materials(root_name, "iris", "hue", props.get("iris_hue", 0))
        apply_hsv_to_materials(root_name, "iris", "saturation", props.get("iris_sat", 0))
        apply_hsv_to_materials(root_name, "iris", "value", props.get("iris_val", 0))

        apply_hsv_to_materials(root_name, "brow", "hue", props.get("brow_hue", 0))
        apply_hsv_to_materials(root_name, "brow", "saturation", props.get("brow_sat", 0))
        apply_hsv_to_materials(root_name, "brow", "value", props.get("brow_val", 0))




def load_character_from_blend(gender, blend_filename):
    loading_text["Text"] = "Loading character from .blend file"
    """
    Para .blend custom: hace append del archivo directamente y lo parenta a characters_holder
    """
    scene = logic.getCurrentScene()
    base_path = os.path.join(bge.logic.expandPath("//"), "Characters", gender, "Exported")
    blend_path = os.path.join(base_path, blend_filename)

    if not os.path.exists(blend_path):
        print(f"[ERROR] No se encontró el archivo {blend_path}")
        return

    # Cargar objetos desde el archivo .blend
    imported_objs = load_blend_objects(blend_path)
    if imported_objs:
        # Buscar y registrar armatures de la misma manera que en el caso de .json
        game_script_holder = scene.objects.get("game_scene_script_holder")
        for obj in imported_objs:
            if obj.type == 'ARMATURE':
                # Renombrar el armature y registrar en 'Armatures'
                register_armature(obj, game_script_holder)
        
        # Parentar objetos a 'characters_holder' (lo mismo que para objetos de .json)
        convert_and_parent(imported_objs, scene, "characters_holder")
        print(f"[INFO] Personaje {blend_filename} cargado correctamente desde {gender}.")









# -------------------- INICIO DEL SCRIPT --------------------

loading_text["Text"] = "Starting load script"

cont = logic.getCurrentController()
own = cont.owner

if not own.get("already_loaded", False):

    # -------------------- CARGA DE ESCENA --------------------
    loading_text["Text"] = "Loading scene"
    
    scene_file = own.get("scene_to_load")
    if scene_file:
        blend_path = os.path.join(bge.logic.expandPath("//"), "Scenes", scene_file)
        if os.path.isfile(blend_path):
            with bpy.data.libraries.load(blend_path, link=False) as (data_src, data_dst):
                data_dst.objects = data_src.objects

            loaded = [obj for obj in data_dst.objects if obj]
            for obj in loaded:
                bpy.context.scene.collection.objects.link(obj)
                try:
                    logic.getCurrentScene().convertBlenderObject(obj)
                except Exception as e:
                    print(f"[ERROR] No se pudo convertir '{obj.name}' a KX_GameObject: {e}")

    # -------------------- CARGA DE PERSONAJES --------------------
    loading_text["Text"] = "Loading characters"
    
    female_file = own.get("female_char", "").strip()
    male_file = own.get("male_char", "").strip()

    if female_file.lower().endswith(".json"):
        load_template_and_apply_json(
            os.path.join(bge.logic.expandPath("//"), "Characters", "Female", "Exported", female_file),
            "female",
            "female_1"
        )
    elif female_file.lower().endswith(".blend"):
        load_character_from_blend("Female", female_file)

    if male_file.lower().endswith(".json"):
        load_template_and_apply_json(
            os.path.join(bge.logic.expandPath("//"), "Characters", "Male", "Exported", male_file),
            "male",
            "man_1"
        )
    elif male_file.lower().endswith(".blend"):
        load_character_from_blend("Male", male_file)

    # -------------------- POST-INICIALIZACIÓN DE CÁMARA --------------------
    
    scene = logic.getCurrentScene()
    objects = scene.objects

    own["already_loaded"] = True
    


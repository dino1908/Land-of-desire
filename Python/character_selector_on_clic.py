# ============================================================
#  UPBGE/BGE - Botón selector con PREVIEW de personajes
#  - Click en botón: setea male_char/female_char en el holder
#  - Limpia previews y carga personaje (JSON o BLEND) en el
#    holder correspondiente, como hijo en (0,0,0) local.
# ============================================================

import bge
import bpy
import json
import os
from bge import logic

# ------------------------------------------------------------
# Utilitarios
# ------------------------------------------------------------

def _scene():
    return logic.getCurrentScene()

def _expand(p):
    return bge.logic.expandPath(p)

def get_kx(name):
    return _scene().objects.get(name)

def clear_children(holder_name):
    """Borra TODOS los hijos (y subhijos) del holder en runtime."""
    holder = get_kx(holder_name)
    if not holder:
        print(f"[WARN] Holder '{holder_name}' no existe.")
        return

    # Copiamos a lista para no modificar mientras iteramos
    # Eliminación recursiva: primero subhijos, luego directos
    # En UPBGE, endObject() elimina el KX_GameObject runtime.
    # Si algo quedó huérfano por parent chain, también cae.
    to_delete = list(holder.children)
    # Barrido ampliado por si hay jerarquías profundas
    idx = 0
    while idx < len(to_delete):
        child = to_delete[idx]
        to_delete.extend(list(child.children))
        idx += 1

    # Eliminar desde el final para evitar dependencias
    for obj in reversed(to_delete):
        try:
            obj.endObject()
        except Exception as e:
            print(f"[WARN] No se pudo borrar hijo '{obj}' de '{holder_name}': {e}")

def load_blend_objects(full_path):
    """Hace append de TODOS los objetos de un .blend a bpy y devuelve la lista bpy de objetos importados."""
    if not os.path.exists(full_path):
        print(f"[ERROR] No existe: {full_path}")
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
        print(f"[ERROR] Falló al cargar '{full_path}': {e}")
        return []

def convert_and_parent(imported_bpy_objs, holder_name):
    """Convierte bpy->KX y parenta a holder con posición local cero."""
    scene = _scene()
    holder = get_kx(holder_name)
    if not holder:
        print(f"[ERROR] Holder '{holder_name}' no encontrado.")
        return []

    converted = []
    for obj in imported_bpy_objs:
        try:
            kx = scene.convertBlenderObject(obj)
            kx.setParent(holder)
            # Centrar en el holder
            kx.localPosition = (0.0, 0.0, 0.0)
            kx.localOrientation = holder.localOrientation.copy()
            converted.append(kx)
        except Exception as e:
            print(f"[ERROR] No se pudo convertir '{obj.name}': {e}")
    return converted

def apply_hsv_to_materials(base_obj_name, keyword, channel, value):
    """Ajusta nodo Hue/Sat de materiales que contengan 'keyword'."""
    obj = bpy.data.objects.get(base_obj_name)
    if not obj:
        print(f"[ERROR] Objeto base '{base_obj_name}' no encontrado para HSV.")
        return

    idx_map = {"hue": 0, "saturation": 1, "value": 2}
    idx = idx_map.get(channel)
    if idx is None:
        print(f"[ERROR] Canal HSV inválido: {channel}")
        return

    def process(o):
        for slot in o.material_slots:
            mat = slot.material
            if not mat:
                continue
            if keyword.lower() in mat.name.lower() and mat.use_nodes:
                hsv_node = next((n for n in mat.node_tree.nodes if n.type == 'HUE_SAT'), None)
                if hsv_node:
                    hsv_node.inputs[idx].default_value = value

    process(obj)
    for ch in obj.children:
        process(ch)

def copy_shape_keys(source_body, target_obj):
    """Replica valores de shape keys por nombre, si existen en ambos."""
    if not source_body or source_body.type != 'MESH':
        return
    if target_obj.type != 'MESH':
        return
    if not (source_body.data.shape_keys and target_obj.data.shape_keys):
        return
    src = source_body.data.shape_keys.key_blocks
    dst = target_obj.data.shape_keys.key_blocks
    for name in dst.keys():
        if name in src:
            dst[name].value = src[name].value

def pick_body_name(imported_bpy_objs, preferred):
    """Intenta usar 'preferred'; si no existe, toma el primer MESH importado como cuerpo."""
    if preferred and bpy.data.objects.get(preferred):
        return preferred
    for o in imported_bpy_objs:
        if o and o.type == 'MESH':
            return o.name
    return None

# ------------------------------------------------------------
# Carga desde JSON (plantilla + piezas + HSV), para PREVIEW
# ------------------------------------------------------------

def load_template_and_apply_json_for_preview(json_path, gender, holder_name):
    gender_l = gender.lower()
    if gender_l not in ("male", "female"):
        print(f"[ERROR] Género inválido '{gender}'.")
        return

    base_dir = _expand("//")
    template_file = "Female_char_template.blend" if gender_l == "female" else "Male_char_template.blend"
    template_path = os.path.join(base_dir, "Characters", template_file)

    # 1) Cargar PLANTILLA base
    template_objs = load_blend_objects(template_path)
    if not template_objs:
        print(f"[ERROR] No se pudo cargar plantilla {template_file}")
        return

    # Elegir nombre del cuerpo (por convención o heurística)
    root_guess = "female_1" if gender_l == "female" else "man_1"
    body_name = pick_body_name(template_objs, root_guess)
    if not body_name:
        print("[ERROR] No se pudo identificar el cuerpo base importado.")
        return

    # Convertir y parentar al holder de preview
    convert_and_parent(template_objs, holder_name)

    # 2) Leer JSON
    if not os.path.exists(json_path):
        print(f"[ERROR] JSON no encontrado: {json_path}")
        return
    with open(json_path, "r") as f:
        data = json.load(f)

    # 3) Aplicar SHAPE KEYS al cuerpo en bpy
    body_obj = bpy.data.objects.get(body_name)
    if body_obj and body_obj.data.shape_keys:
        for key_name, val in data.get("shape_keys", {}).items():
            if key_name in body_obj.data.shape_keys.key_blocks:
                body_obj.data.shape_keys.key_blocks[key_name].value = val

    # 4) Importar PARTES declaradas en JSON y parentarlas al holder
    base_dirs = {
        "male":   os.path.join(base_dir, "Characters", "Male"),
        "female": os.path.join(base_dir, "Characters", "Female"),
    }
    folder_map = {
        "hair": "Hairs",
        "pants": "Clothes/Pants",
        "shoes": "Clothes/Shoes",
        "torso_up": "Clothes/Torso",
    }

    for part, blend_file in data.get("blend_files", {}).items():
        if not blend_file:
            continue
        subdir = folder_map.get(part)
        if not subdir:
            print(f"[WARN] Parte desconocida en JSON: {part}")
            continue

        part_path = os.path.join(base_dirs[gender_l], subdir, blend_file)
        part_objs = load_blend_objects(part_path)
        if not part_objs:
            print(f"[WARN] No se pudo importar parte '{part}' desde {part_path}")
            continue

        # Sin registrar armatures en ningún holder global (solo preview)
        # Copiar shape keys del cuerpo si corresponden
        for o in part_objs:
            try:
                copy_shape_keys(body_obj, o)
            except Exception as e:
                print(f"[WARN] copy_shape_keys('{o.name}') falló: {e}")

        convert_and_parent(part_objs, holder_name)

    # 5) HSV a materiales (si hay propiedades en JSON)
    props = data.get("properties", {})
    try:
        apply_hsv_to_materials(body_name, "skin", "hue",        props.get("skin_hue", 0))
        apply_hsv_to_materials(body_name, "skin", "saturation", props.get("skin_sat", 0))
        apply_hsv_to_materials(body_name, "skin", "value",      props.get("skin_val", 0))

        apply_hsv_to_materials(body_name, "iris", "hue",        props.get("iris_hue", 0))
        apply_hsv_to_materials(body_name, "iris", "saturation", props.get("iris_sat", 0))
        apply_hsv_to_materials(body_name, "iris", "value",      props.get("iris_val", 0))

        apply_hsv_to_materials(body_name, "brow", "hue",        props.get("brow_hue", 0))
        apply_hsv_to_materials(body_name, "brow", "saturation", props.get("brow_sat", 0))
        apply_hsv_to_materials(body_name, "brow", "value",      props.get("brow_val", 0))
    except Exception as e:
        print(f"[WARN] Aplicación de HSV falló: {e}")

    print(f"[OK] Preview JSON '{os.path.basename(json_path)}' cargado en '{holder_name}'.")

# ------------------------------------------------------------
# Carga directa desde .blend, para PREVIEW
# ------------------------------------------------------------

def load_preview_from_blend(gender, blend_filename, holder_name):
    gender_cap = "Female" if gender.lower() == "female" else "Male"
    base_dir = _expand("//")
    blend_path = os.path.join(base_dir, "Characters", gender_cap, "Exported", blend_filename)

    imported = load_blend_objects(blend_path)
    if not imported:
        print(f"[ERROR] No se pudo cargar '{blend_filename}'")
        return

    convert_and_parent(imported, holder_name)
    print(f"[OK] Preview BLEND '{blend_filename}' cargado en '{holder_name}'.")

# ------------------------------------------------------------
# Manejador de clic en el botón
# ------------------------------------------------------------

cont = logic.getCurrentController()
own = cont.owner  # botón

mouse_clic = cont.sensors.get("MouseClick")
mouse_over = cont.sensors.get("MouseOver")

if mouse_clic and mouse_over and mouse_clic.positive and mouse_over.positive:
    scene = _scene()
    target = scene.objects.get("character_selector_script_holder")
    if not target:
        print("[ERROR] No se encontró 'character_selector_script_holder'")

    # Validaciones mínimas
    if "file" not in own or "gender" not in own:
        print("[ERROR] El botón no tiene propiedades 'file' y/o 'gender'.")
        # Sigo pero probablemente no haya nada que cargar
    filename = str(own.get("file", "")).strip()
    gender   = str(own.get("gender", "")).strip().lower()

    # Seteo de propiedades en el holder, como tu script original
    if target and filename:
        if gender == "male":
            target["male_char"] = filename
        elif gender == "female":
            target["female_char"] = filename
        else:
            print(f"[ERROR] Género desconocido '{gender}'")

    # Limpiar SIEMPRE ambos holders de preview antes de importar

    

    # Decidir holder de destino según género clickeado
    holder_name = None
    if gender == "male":
        clear_children("male_preview_holder")
        holder_name = "male_preview_holder"
    elif gender == "female":
        clear_children("female_preview_holder")
        holder_name = "female_preview_holder"

    if not holder_name:
        print(f"[ERROR] No se puede determinar holder para género '{gender}'.")
    elif not filename:
        print("[ERROR] Propiedad 'file' vacía; no hay nada que cargar.")
    else:
        # Resolver ruta y cargar según extensión
        base_dir = _expand("//")
        if filename.lower().endswith(".json"):
            json_path = os.path.join(
                base_dir, "Characters",
                "Female" if gender == "female" else "Male",
                "Exported", filename
            )
            load_template_and_apply_json_for_preview(json_path, gender, holder_name)

        elif filename.lower().endswith(".blend"):
            load_preview_from_blend(gender, filename, holder_name)

        else:
            print(f"[ERROR] Extensión no soportada en '{filename}'. Solo .json o .blend.")


#import bge

#cont = bge.logic.getCurrentController()
#own = cont.owner  # El botón que fue clickeado

#mouse_clic = cont.sensors["MouseClick"]
#mouse_over = cont.sensors["MouseOver"]

#if mouse_clic.positive and mouse_over.positive:
#    scene = bge.logic.getCurrentScene()
#    target = scene.objects.get("character_selector_script_holder")
#    if not target:
#        print("ERROR: No se encontró 'character_selector_script_holder'")
#       

#    # Validar que el botón tenga propiedades válidas
#    if "file" not in own or "gender" not in own:
#        print("ERROR: El botón no tiene 'file' o 'gender'")
#        

#    filename = own["file"]
#    gender = own["gender"]

#    if gender == "male":
#        target["male_char"] = filename
#      #  print(f"Asignado male_char = {filename}")
#    elif gender == "female":
#        target["female_char"] = filename
#     #   print(f"Asignado female_char = {filename}")
#    else:
#        print(f"ERROR: género desconocido '{gender}'")

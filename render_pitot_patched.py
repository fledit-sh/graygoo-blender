"""
Premium studio render setup for the UBIQ Aerospace pitot probe.

Highlights:
- Robust STL import workflow with filename-based material assignment.
- Pure black world background for predictable PNG output.
- Procedural brushed aluminum and satin black polymer materials.
- Premium dark-studio lighting with controlled edge definition.
- Clean three-quarter hero-shot camera composition.
"""

import bpy
import math
import os
from mathutils import Vector


# ══════════════════════════════════════════════════════════════
#  ▶▶ SETTINGS ◀◀
# ══════════════════════════════════════════════════════════════

# Leave empty for automatic path detection relative to the script /.blend file.
MANUAL_PARTS_DIR = ""

PREVIEW_MODE = True
USE_EXPLODED_VIEW = False
EXPLODE_AXIS = "X"
EXPLODE_GAP = 0.028  # Meters after STL import (global_scale=0.001)

# Pure black background for stable catalog output.
BACKGROUND_COLOR = (0.0, 0.0, 0.0, 1.0)

if PREVIEW_MODE:
    RENDER_WIDTH, RENDER_HEIGHT, RENDER_SAMPLES, OUTPUT_SUFFIX = 1280, 720, 64, "_preview"
else:
    RENDER_WIDTH, RENDER_HEIGHT, RENDER_SAMPLES, OUTPUT_SUFFIX = 2560, 1440, 320, ""

PARTS = [
    ("00_total_pressure_port.stl", "brushed_aluminum", "Total Pressure Port"),
    ("01_main_housing.stl", "black_satin_plastic", "Main Housing"),
    ("02_base_plate.stl", "black_satin_plastic", "Base Plate"),
    ("03_static_port.stl", "black_satin_plastic", "Static Port"),
    ("04_fitting.stl", "brushed_aluminum", "Fitting"),
]


# ── Path discovery ───────────────────────────────────────────

def get_script_directory():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        pass

    for text in bpy.data.texts:
        if text.filepath:
            return os.path.dirname(bpy.path.abspath(text.filepath))

    if bpy.data.filepath:
        return os.path.dirname(bpy.data.filepath)

    return os.getcwd()



def get_parts_dir():
    candidates = []

    if MANUAL_PARTS_DIR:
        candidates.extend(
            [
                os.path.join(MANUAL_PARTS_DIR, "parts_obj"),
                MANUAL_PARTS_DIR,
            ]
        )

    script_dir = get_script_directory()
    candidates.extend(
        [
            os.path.join(script_dir, "parts_obj"),
            script_dir,
        ]
    )

    if bpy.data.filepath:
        blend_dir = os.path.dirname(bpy.data.filepath)
        candidates.extend(
            [
                os.path.join(blend_dir, "parts_obj"),
                blend_dir,
            ]
        )

    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        candidate = os.path.normpath(candidate)
        if candidate in seen:
            continue
        seen.add(candidate)
        if not os.path.isdir(candidate):
            continue

        filenames = {entry.lower() for entry in os.listdir(candidate)}
        if "parts_obj" not in os.path.basename(candidate).lower():
            nested = os.path.join(candidate, "parts_obj")
            if os.path.isdir(nested):
                nested_names = {entry.lower() for entry in os.listdir(nested)}
                if "00_total_pressure_port.stl" in nested_names:
                    return nested

        if "00_total_pressure_port.stl" in filenames:
            return candidate

    return None


# ── Utility helpers ──────────────────────────────────────────

def socket(node, *names):
    for name in names:
        if name in node.inputs:
            return node.inputs[name]
    return None



def clear_node_tree(node_tree):
    for node in list(node_tree.nodes):
        node_tree.nodes.remove(node)



def safe_remove(block_collection, block):
    try:
        block_collection.remove(block)
    except Exception:
        pass



def object_bounds_world(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    xs = [co.x for co in corners]
    ys = [co.y for co in corners]
    zs = [co.z for co in corners]
    return (
        Vector((min(xs), min(ys), min(zs))),
        Vector((max(xs), max(ys), max(zs))),
    )



def object_dimensions_local(obj):
    corners = [Vector(corner) for corner in obj.bound_box]
    mins = Vector((min(c[i] for c in corners) for i in range(3)))
    maxs = Vector((max(c[i] for c in corners) for i in range(3)))
    center = (mins + maxs) * 0.5
    size = maxs - mins
    return center, size



def ensure_object_mode():
    active = bpy.context.active_object
    if active and active.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")



def set_socket_value(node, names, value):
    target = socket(node, *names)
    if target is not None:
        target.default_value = value



def link_if_possible(node_tree, from_socket, to_socket):
    if from_socket is not None and to_socket is not None:
        node_tree.links.new(from_socket, to_socket)


# ── Materials ────────────────────────────────────────────────

def make_brushed_aluminum_material(name):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    clear_node_tree(nt)

    nodes = nt.nodes
    links = nt.links

    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    texcoord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    wave = nodes.new("ShaderNodeTexWave")
    noise = nodes.new("ShaderNodeTexNoise")
    roughness_mix = nodes.new("ShaderNodeMixRGB")
    roughness_ramp = nodes.new("ShaderNodeValToRGB")
    bump = nodes.new("ShaderNodeBump")
    fine_bump = nodes.new("ShaderNodeBump")
    detail_noise = nodes.new("ShaderNodeTexNoise")
    detail_ramp = nodes.new("ShaderNodeValToRGB")
    metal_tint = nodes.new("ShaderNodeRGB")

    output.location = (920, 40)
    bsdf.location = (620, 40)
    texcoord.location = (-980, -20)
    mapping.location = (-770, -20)
    wave.location = (-540, 160)
    noise.location = (-540, -80)
    roughness_mix.location = (-250, 110)
    roughness_ramp.location = (20, 120)
    detail_noise.location = (-260, -220)
    detail_ramp.location = (10, -220)
    bump.location = (300, -70)
    fine_bump.location = (440, -180)
    metal_tint.location = (300, 260)

    mapping.inputs[3].default_value = (0.0, 0.0, math.radians(90.0))
    mapping.inputs[4].default_value = (28.0, 4.0, 4.0)

    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.rings_direction = "X"
    wave.inputs[1].default_value = 16.0
    wave.inputs[2].default_value = 1.3
    wave.inputs[3].default_value = 1.5

    noise.inputs[2].default_value = 8.0
    noise.inputs[3].default_value = 2.0
    noise.inputs[4].default_value = 0.55

    roughness_mix.blend_type = "MULTIPLY"
    roughness_mix.inputs[0].default_value = 0.35

    roughness_ramp.color_ramp.elements[0].position = 0.34
    roughness_ramp.color_ramp.elements[0].color = (0.12, 0.12, 0.12, 1.0)
    roughness_ramp.color_ramp.elements[1].position = 0.78
    roughness_ramp.color_ramp.elements[1].color = (0.28, 0.28, 0.28, 1.0)

    detail_noise.inputs[2].default_value = 180.0
    detail_noise.inputs[3].default_value = 5.0
    detail_noise.inputs[4].default_value = 0.2

    detail_ramp.color_ramp.elements[0].position = 0.44
    detail_ramp.color_ramp.elements[0].color = (0.44, 0.44, 0.44, 1.0)
    detail_ramp.color_ramp.elements[1].position = 0.58
    detail_ramp.color_ramp.elements[1].color = (0.56, 0.56, 0.56, 1.0)

    bump.inputs[0].default_value = 0.18
    bump.inputs[1].default_value = 0.015
    fine_bump.inputs[0].default_value = 0.06
    fine_bump.inputs[1].default_value = 0.0025

    metal_tint.outputs[0].default_value = (0.78, 0.79, 0.81, 1.0)

    set_socket_value(bsdf, ("Metallic",), 1.0)
    set_socket_value(bsdf, ("Roughness",), 0.19)
    set_socket_value(bsdf, ("Base Color",), (0.78, 0.79, 0.81, 1.0))
    set_socket_value(bsdf, ("Anisotropic",), 0.72)
    set_socket_value(bsdf, ("Anisotropic Rotation",), 0.08)
    set_socket_value(bsdf, ("Specular IOR Level", "Specular"), 0.55)
    set_socket_value(bsdf, ("Coat Weight", "Clearcoat"), 0.02)
    set_socket_value(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.08)

    links.new(texcoord.outputs["Object"], mapping.inputs[0])
    links.new(mapping.outputs["Vector"], wave.inputs[0])
    links.new(mapping.outputs["Vector"], noise.inputs[0])
    links.new(mapping.outputs["Vector"], detail_noise.inputs[0])
    links.new(wave.outputs["Color"], roughness_mix.inputs[1])
    links.new(noise.outputs["Fac"], roughness_mix.inputs[2])
    links.new(roughness_mix.outputs["Color"], roughness_ramp.inputs["Fac"])
    links.new(roughness_ramp.outputs["Color"], bump.inputs[2])
    links.new(detail_ramp.outputs["Color"], fine_bump.inputs[2])
    links.new(detail_noise.outputs["Fac"], detail_ramp.inputs["Fac"])
    links.new(bump.outputs["Normal"], fine_bump.inputs["Normal"])
    links.new(metal_tint.outputs["Color"], bsdf.inputs["Base Color"])
    link_if_possible(nt, roughness_ramp.outputs["Color"], socket(bsdf, "Roughness"))
    link_if_possible(nt, fine_bump.outputs["Normal"], socket(bsdf, "Normal"))
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    return mat



def make_black_satin_plastic_material(name):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    clear_node_tree(nt)

    nodes = nt.nodes
    links = nt.links

    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    texcoord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    noise = nodes.new("ShaderNodeTexNoise")
    musgrave = nodes.new("ShaderNodeTexMusgrave")
    roughness_mix = nodes.new("ShaderNodeMixRGB")
    roughness_ramp = nodes.new("ShaderNodeValToRGB")
    bump = nodes.new("ShaderNodeBump")
    color_mix = nodes.new("ShaderNodeMixRGB")
    dark_rgb = nodes.new("ShaderNodeRGB")
    edge_rgb = nodes.new("ShaderNodeRGB")

    output.location = (890, 40)
    bsdf.location = (610, 40)
    texcoord.location = (-930, 0)
    mapping.location = (-720, 0)
    noise.location = (-500, 130)
    musgrave.location = (-500, -120)
    roughness_mix.location = (-250, 70)
    roughness_ramp.location = (20, 80)
    bump.location = (270, -120)
    color_mix.location = (280, 240)
    dark_rgb.location = (20, 300)
    edge_rgb.location = (20, 190)

    mapping.inputs[4].default_value = (9.0, 9.0, 9.0)

    noise.inputs[2].default_value = 7.0
    noise.inputs[3].default_value = 2.0
    noise.inputs[4].default_value = 0.45

    if hasattr(musgrave, "musgrave_type"):
        musgrave.musgrave_type = "RIDGED_MULTIFRACTAL"
    musgrave.inputs[2].default_value = 24.0
    musgrave.inputs[3].default_value = 5.0
    musgrave.inputs[4].default_value = 0.45

    roughness_mix.blend_type = "SOFT_LIGHT"
    roughness_mix.inputs[0].default_value = 0.55

    roughness_ramp.color_ramp.elements[0].position = 0.24
    roughness_ramp.color_ramp.elements[0].color = (0.28, 0.28, 0.28, 1.0)
    roughness_ramp.color_ramp.elements[1].position = 0.78
    roughness_ramp.color_ramp.elements[1].color = (0.48, 0.48, 0.48, 1.0)

    bump.inputs[0].default_value = 0.12
    bump.inputs[1].default_value = 0.0016

    color_mix.blend_type = "MIX"
    color_mix.inputs[0].default_value = 0.18
    dark_rgb.outputs[0].default_value = (0.02, 0.02, 0.022, 1.0)
    edge_rgb.outputs[0].default_value = (0.05, 0.05, 0.055, 1.0)

    set_socket_value(bsdf, ("Metallic",), 0.0)
    set_socket_value(bsdf, ("Roughness",), 0.38)
    set_socket_value(bsdf, ("Base Color",), (0.022, 0.022, 0.024, 1.0))
    set_socket_value(bsdf, ("IOR",), 1.48)
    set_socket_value(bsdf, ("Specular IOR Level", "Specular"), 0.42)
    set_socket_value(bsdf, ("Coat Weight", "Clearcoat"), 0.03)
    set_socket_value(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.22)
    set_socket_value(bsdf, ("Sheen Weight", "Sheen"), 0.03)
    set_socket_value(bsdf, ("Sheen Roughness",), 0.55)

    links.new(texcoord.outputs["Object"], mapping.inputs[0])
    links.new(mapping.outputs["Vector"], noise.inputs[0])
    links.new(mapping.outputs["Vector"], musgrave.inputs[0])
    links.new(noise.outputs["Fac"], roughness_mix.inputs[1])
    links.new(musgrave.outputs["Fac"], roughness_mix.inputs[2])
    links.new(roughness_mix.outputs["Color"], roughness_ramp.inputs["Fac"])
    links.new(roughness_ramp.outputs["Color"], bump.inputs[2])
    links.new(dark_rgb.outputs["Color"], color_mix.inputs[1])
    links.new(edge_rgb.outputs["Color"], color_mix.inputs[2])
    links.new(musgrave.outputs["Fac"], color_mix.inputs[0])
    links.new(color_mix.outputs["Color"], bsdf.inputs["Base Color"])
    link_if_possible(nt, roughness_ramp.outputs["Color"], socket(bsdf, "Roughness"))
    link_if_possible(nt, bump.outputs["Normal"], socket(bsdf, "Normal"))
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    return mat



def build_materials():
    return {
        "brushed_aluminum": make_brushed_aluminum_material("MAT_BrushedAluminum"),
        "black_satin_plastic": make_black_satin_plastic_material("MAT_BlackSatinPlastic"),
    }


# ── Import ───────────────────────────────────────────────────

def import_stl(filepath):
    bpy.ops.object.select_all(action="DESELECT")

    operators = []
    if hasattr(bpy.ops.wm, "stl_import"):
        operators.append(lambda: bpy.ops.wm.stl_import(filepath=filepath, global_scale=0.001))
    if hasattr(bpy.ops.import_mesh, "stl"):
        operators.append(lambda: bpy.ops.import_mesh.stl(filepath=filepath, global_scale=0.001))

    for operation in operators:
        try:
            operation()
            selected = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
            return selected[0] if selected else None
        except Exception as exc:
            print(f"    [WARN] STL import operator failed: {exc}")

    print(f"    [ERROR] STL import failed: {filepath}")
    return None



def smooth_object(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
    except Exception:
        try:
            bpy.ops.object.shade_smooth()
        except Exception:
            pass
    obj.select_set(False)


# ── Scene setup ──────────────────────────────────────────────

def cleanup_scene():
    ensure_object_mode()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    datablocks = (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.curves,
        bpy.data.images,
    )
    for blocks in datablocks:
        for block in list(blocks):
            if getattr(block, "users", 0) == 0:
                safe_remove(blocks, block)



def setup_world():
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("StudioWorld")

    world = scene.world
    world.use_nodes = True
    nt = world.node_tree
    clear_node_tree(nt)

    output = nt.nodes.new("ShaderNodeOutputWorld")
    background = nt.nodes.new("ShaderNodeBackground")

    output.location = (250, 0)
    background.location = (0, 0)

    background.inputs["Color"].default_value = BACKGROUND_COLOR
    background.inputs["Strength"].default_value = 1.0
    nt.links.new(background.outputs["Background"], output.inputs["Surface"])

    print("  [World] Pure black world background configured")



def add_area_light(name, location, rotation, energy, size_x, size_y, color, spread=math.radians(120.0)):
    bpy.ops.object.light_add(type="AREA", location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.shape = "RECTANGLE"
    obj.data.energy = energy
    obj.data.size = size_x
    if hasattr(obj.data, "size_y"):
        obj.data.size_y = size_y
    obj.data.color = color
    if hasattr(obj.data, "spread"):
        obj.data.spread = spread
    return obj



def setup_lighting(center, size, min_corner, max_corner):
    setup_world()

    span = max(size.x, size.y, size.z, 0.08)
    cx, cy, cz = center.x, center.y, center.z
    z_top = max_corner.z
    z_low = min_corner.z

    key_energy = 2400 if PREVIEW_MODE else 3600
    fill_energy = 500 if PREVIEW_MODE else 850
    rim_energy = 1500 if PREVIEW_MODE else 2400
    kicker_energy = 900 if PREVIEW_MODE else 1350

    add_area_light(
        "Key Softbox",
        (cx + span * 1.45, cy - span * 1.85, z_top + span * 0.85),
        (math.radians(62.0), 0.0, math.radians(-34.0)),
        energy=key_energy,
        size_x=span * 1.20,
        size_y=span * 0.58,
        color=(1.0, 0.985, 0.965),
    )
    add_area_light(
        "Fill Softbox",
        (cx - span * 1.85, cy - span * 0.55, cz + span * 0.40),
        (math.radians(86.0), 0.0, math.radians(60.0)),
        energy=fill_energy,
        size_x=span * 1.65,
        size_y=span * 0.85,
        color=(0.84, 0.90, 1.0),
    )
    add_area_light(
        "Rim Strip",
        (cx + span * 0.25, cy + span * 1.95, z_top + span * 0.55),
        (math.radians(-68.0), 0.0, math.radians(4.0)),
        energy=rim_energy,
        size_x=span * 0.34,
        size_y=span * 1.70,
        color=(1.0, 1.0, 1.0),
    )
    add_area_light(
        "Lower Kicker",
        (cx - span * 0.15, cy - span * 1.25, z_low + span * 0.10),
        (math.radians(104.0), 0.0, math.radians(4.0)),
        energy=kicker_energy,
        size_x=span * 0.55,
        size_y=span * 0.26,
        color=(0.92, 0.96, 1.0),
        spread=math.radians(100.0),
    )

    print(f"  [Light] Premium studio setup created for span={span:.4f}m")



def compute_bounds(objects):
    mins = []
    maxs = []
    for obj in objects:
        obj_min, obj_max = object_bounds_world(obj)
        mins.append(obj_min)
        maxs.append(obj_max)

    if not mins:
        return None

    min_corner = Vector((min(v.x for v in mins), min(v.y for v in mins), min(v.z for v in mins)))
    max_corner = Vector((max(v.x for v in maxs), max(v.y for v in maxs), max(v.z for v in maxs)))
    center = (min_corner + max_corner) * 0.5
    size = max_corner - min_corner
    diag = size.length

    print(
        "  [Bounds] center=(%.4f, %.4f, %.4f) size=(%.4f, %.4f, %.4f) diag=%.4f"
        % (center.x, center.y, center.z, size.x, size.y, size.z, diag)
    )
    return center, size, min_corner, max_corner



def layout_exploded(objects, axis="X", gap=0.03):
    axis_index = "XYZ".index(axis.upper())
    spans = []
    for obj in objects:
        local_center, local_size = object_dimensions_local(obj)
        spans.append((obj, local_center, local_size[axis_index]))

    total_span = sum(span for _, _, span in spans) + gap * max(len(spans) - 1, 0)
    cursor = -total_span * 0.5

    for obj, local_center, span in spans:
        target_center = cursor + span * 0.5
        current_center = obj.location[axis_index] + local_center[axis_index]
        obj.location[axis_index] += target_center - current_center
        cursor += span + gap
        print(f"  [Explode] {obj.name:<22} -> {axis}={obj.location[axis_index]:.4f}")



def setup_camera(bounds):
    center, size, min_corner, max_corner = bounds
    span = max(size.x, size.y, size.z, 0.08)

    # Slight front-left three-quarter framing gives the probe depth while keeping the silhouette clean.
    look_at = Vector(
        (
            center.x - size.x * 0.03,
            center.y + size.y * 0.01,
            center.z + size.z * 0.04,
        )
    )
    cam_offset = Vector((-span * 1.55, -span * 2.65, span * 0.82))
    cam_pos = look_at + cam_offset

    bpy.ops.object.camera_add(location=cam_pos)
    cam = bpy.context.object
    cam.name = "PitotCamera"
    cam.rotation_euler = (look_at - cam_pos).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 80 if PREVIEW_MODE else 92
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.001
    cam.data.clip_end = 1000
    cam.data.dof.use_dof = False

    scene = bpy.context.scene
    scene.camera = cam

    # Keep the product comfortably within frame without relying on manual view operators.
    margin = 1.18
    horizontal_span = max(size.x, size.y) * margin
    vertical_span = size.z * margin
    lens_factor = max(horizontal_span / 2.0, vertical_span / 1.15)
    if lens_factor > 0:
        desired_distance = max(cam_offset.length, lens_factor * 4.1)
        view_dir = (cam_pos - look_at).normalized()
        cam.location = look_at + view_dir * desired_distance
        cam.rotation_euler = (look_at - cam.location).to_track_quat("-Z", "Y").to_euler()

    print(
        "  [Camera] lens=%smm location=(%.4f, %.4f, %.4f) target=(%.4f, %.4f, %.4f)"
        % (
            cam.data.lens,
            cam.location.x,
            cam.location.y,
            cam.location.z,
            look_at.x,
            look_at.y,
            look_at.z,
        )
    )
    print(
        "  [Frame] object extents x=%.4f y=%.4f z=%.4f / min_z=%.4f max_z=%.4f"
        % (size.x, size.y, size.z, min_corner.z, max_corner.z)
    )


# ── Render setup ─────────────────────────────────────────────

def setup_cycles_devices(scene):
    preferences = bpy.context.preferences
    cycles_addon = preferences.addons.get("cycles")
    if cycles_addon is None:
        scene.cycles.device = "CPU"
        print("  [GPU] Cycles addon not found -> CPU")
        return

    cprefs = cycles_addon.preferences
    for device_type in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            cprefs.compute_device_type = device_type
            refresh = getattr(cprefs, "refresh_devices", None)
            if refresh:
                refresh()
            elif hasattr(cprefs, "get_devices"):
                cprefs.get_devices()

            if not getattr(cprefs, "devices", None):
                continue

            for device in cprefs.devices:
                device.use = True

            scene.cycles.device = "GPU"
            print(f"  [GPU] Using {device_type}")
            return
        except Exception as exc:
            print(f"  [GPU] {device_type} unavailable: {exc}")

    scene.cycles.device = "CPU"
    print("  [GPU] No GPU available -> CPU")



def setup_render(render_out):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = RENDER_WIDTH
    scene.render.resolution_y = RENDER_HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.filepath = render_out
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False

    scene.cycles.samples = RENDER_SAMPLES
    scene.cycles.preview_samples = min(RENDER_SAMPLES, 64)
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 10
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 6
    scene.cycles.transmission_bounces = 4
    scene.cycles.transparent_max_bounces = 8
    scene.cycles.filter_width = 0.75

    if hasattr(scene.cycles, "use_fast_gi"):
        scene.cycles.use_fast_gi = False
    if hasattr(scene.cycles, "caustics_reflective"):
        scene.cycles.caustics_reflective = False
    if hasattr(scene.cycles, "caustics_refractive"):
        scene.cycles.caustics_refractive = False

    if PREVIEW_MODE:
        scene.cycles.device = "CPU"
        print("  [Render] Preview mode -> CPU for predictable quick checks")
    else:
        setup_cycles_devices(scene)

    display_settings = scene.display_settings
    view_settings = scene.view_settings
    display_settings.display_device = "sRGB"

    for transform in ("AgX", "Filmic", "Standard"):
        try:
            view_settings.view_transform = transform
            print(f"  [CM] View Transform: {transform}")
            break
        except Exception:
            continue

    for look in (
        "AgX - Medium High Contrast",
        "AgX - Base Contrast",
        "Medium High Contrast",
        "None",
    ):
        try:
            view_settings.look = look
            print(f"  [CM] Look: {look}")
            break
        except Exception:
            continue

    view_settings.exposure = -0.20
    view_settings.gamma = 1.0

    print(f"  [Render] {RENDER_WIDTH}x{RENDER_HEIGHT}, {RENDER_SAMPLES}spp -> {render_out}")


# ── Main program ─────────────────────────────────────────────

def main():
    mode_label = "PREVIEW" if PREVIEW_MODE else "FINAL"
    print("\n" + "=" * 60)
    print(f"  PITOT PROBE – {mode_label} ({RENDER_WIDTH}x{RENDER_HEIGHT}, {RENDER_SAMPLES}spp)")
    print("=" * 60)

    parts_dir = get_parts_dir()
    if not parts_dir:
        print(f"\n[ERROR] parts_obj not found. MANUAL_PARTS_DIR='{MANUAL_PARTS_DIR}'")
        return

    render_out = os.path.join(os.path.dirname(parts_dir), f"pitot_render{OUTPUT_SUFFIX}.png")
    print(f"  [Input]  {parts_dir}")
    print(f"  [Output] {render_out}")

    cleanup_scene()
    materials = build_materials()

    print("\nImporting parts...")
    objects = []
    for filename, material_key, label in PARTS:
        filepath = os.path.join(parts_dir, filename)
        if not os.path.exists(filepath):
            print(f"  [SKIP] Missing file: {filename}")
            continue

        obj = import_stl(filepath)
        if obj is None:
            print(f"  [ERROR] Failed to import: {filename}")
            continue

        obj.name = label
        smooth_object(obj)
        obj.data.materials.clear()
        obj.data.materials.append(materials[material_key])
        objects.append(obj)
        print(f"  [OK]   {label:<22} -> {material_key}")

    if not objects:
        print("\n[ERROR] No parts were imported.")
        return

    if USE_EXPLODED_VIEW and len(objects) > 1:
        print("\nApplying exploded view...")
        layout_exploded(objects, axis=EXPLODE_AXIS, gap=EXPLODE_GAP)

    print("\nScene setup...")
    bounds = compute_bounds(objects)
    if bounds is None:
        print("[ERROR] Unable to compute bounding box.")
        return

    center, size, min_corner, max_corner = bounds
    setup_lighting(center, size, min_corner, max_corner)
    setup_camera(bounds)
    setup_render(render_out)

    print("\n" + "=" * 60)
    print("  Rendering...")
    print("=" * 60 + "\n")
    bpy.ops.render.render(write_still=True)
    print(f"\n[DONE] -> {render_out}")


main()

"""
Premium studio render setup for the UBIQ Aerospace pitot probe.

What changed and why:
- Rebuilt the render environment so Cycles behaves more like a curated studio HDRI setup,
  while the camera still sees a black background.
- Added glossy-only reflection cards plus tuned area lights so aluminum gets richer highlights
  and the black polymer keeps readable specular separation without washing out to grey.
- Reworked the materials: aluminum now has stronger anisotropic brushing/contrast, and the
  black plastic stays deeper with a subtle SLS-style micro texture.
- Added a near-invisible reflection floor patch under the probe for premium contact/reflection
  without turning the whole scene into a grey stage.
- Tightened color management for a darker, cleaner, higher-contrast hero render.

This script is fully self-contained and intended to run without manual scene tweaks.
"""

import bpy
import math
import os
from mathutils import Vector


# ══════════════════════════════════════════════════════════════
#  ▶▶ SETTINGS / EASY TWEAKS ◀◀
# ══════════════════════════════════════════════════════════════

# Leave empty for automatic path detection relative to the script /.blend file.
MANUAL_PARTS_DIR = ""

# Quality mode toggle kept simple for script-only workflows.
PREVIEW_MODE = True
USE_EXPLODED_VIEW = False
EXPLODE_AXIS = "X"
EXPLODE_GAP = 0.028  # Meters after STL import (global_scale=0.001)

# Main artistic controls requested for easy iteration.
BACKGROUND_MODE = "BLACK_CAMERA_STUDIO"  # BLACK_CAMERA_STUDIO / PURE_BLACK
REFLECTION_FLOOR_STRENGTH = 0.18         # 0.0 = off, ~0.12-0.28 = subtle premium contact
STUDIO_REFLECTION_INTENSITY = 1.25       # Raises reflection-card/world reflection presence
BLACK_PLASTIC_DARKNESS = 0.92            # Higher = darker plastic
ALUMINUM_CONTRAST = 1.18                 # Higher = stronger brushed contrast

# Camera-facing background should remain visually black.
BACKGROUND_COLOR = (0.0, 0.0, 0.0, 1.0)

if PREVIEW_MODE:
    RENDER_WIDTH, RENDER_HEIGHT, RENDER_SAMPLES, OUTPUT_SUFFIX = 1280, 720, 96, "_preview"
else:
    RENDER_WIDTH, RENDER_HEIGHT, RENDER_SAMPLES, OUTPUT_SUFFIX = 2560, 1440, 384, ""

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



def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))



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



def set_visibility_flag(obj, name, value):
    cycles_visibility = getattr(obj, "cycles_visibility", None)
    if cycles_visibility is not None and hasattr(cycles_visibility, name):
        setattr(cycles_visibility, name, value)

    legacy_name = f"visible_{name}"
    if hasattr(obj, legacy_name):
        setattr(obj, legacy_name, value)



def set_object_ray_visibility(obj, *, camera=None, diffuse=None, glossy=None, transmission=None, shadow=None, scatter=None):
    values = {
        "camera": camera,
        "diffuse": diffuse,
        "glossy": glossy,
        "transmission": transmission,
        "shadow": shadow,
        "scatter": scatter,
    }
    for name, value in values.items():
        if value is not None:
            set_visibility_flag(obj, name, value)



def look_at_rotation(location, target):
    return (target - location).to_track_quat("-Z", "Y").to_euler()


# ── Materials ────────────────────────────────────────────────

def make_brushed_aluminum_material(name):
    """Brushed aluminum with stronger anisotropic readability for hero shots."""
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
    detail_noise = nodes.new("ShaderNodeTexNoise")
    blend = nodes.new("ShaderNodeMixRGB")
    contrast = nodes.new("ShaderNodeBrightContrast")
    roughness_ramp = nodes.new("ShaderNodeValToRGB")
    detail_ramp = nodes.new("ShaderNodeValToRGB")
    bump = nodes.new("ShaderNodeBump")
    micro_bump = nodes.new("ShaderNodeBump")
    tint = nodes.new("ShaderNodeRGB")

    output.location = (980, 40)
    bsdf.location = (680, 40)
    texcoord.location = (-980, 0)
    mapping.location = (-760, 0)
    wave.location = (-540, 180)
    noise.location = (-540, -20)
    detail_noise.location = (-540, -240)
    blend.location = (-260, 100)
    contrast.location = (-30, 100)
    roughness_ramp.location = (210, 100)
    detail_ramp.location = (-260, -240)
    bump.location = (210, -120)
    micro_bump.location = (430, -140)
    tint.location = (410, 250)

    # Large-scale directionality establishes the brushed read, while the subtle noise prevents CG-flatness.
    mapping.inputs[3].default_value = (0.0, 0.0, math.radians(90.0))
    mapping.inputs[4].default_value = (32.0, 4.5, 4.5)

    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs[1].default_value = 20.0
    wave.inputs[2].default_value = 1.8
    wave.inputs[3].default_value = 1.9

    noise.inputs[2].default_value = 10.0
    noise.inputs[3].default_value = 2.0
    noise.inputs[4].default_value = 0.45

    detail_noise.inputs[2].default_value = 240.0
    detail_noise.inputs[3].default_value = 5.0
    detail_noise.inputs[4].default_value = 0.15

    blend.blend_type = "MULTIPLY"
    blend.inputs[0].default_value = 0.40

    contrast.inputs[1].default_value = 0.0
    contrast.inputs[2].default_value = 2.0 * (ALUMINUM_CONTRAST - 1.0)

    roughness_ramp.color_ramp.elements[0].position = 0.28
    roughness_ramp.color_ramp.elements[0].color = (0.07, 0.07, 0.07, 1.0)
    roughness_ramp.color_ramp.elements[1].position = 0.76
    roughness_ramp.color_ramp.elements[1].color = (0.24, 0.24, 0.24, 1.0)

    detail_ramp.color_ramp.elements[0].position = 0.42
    detail_ramp.color_ramp.elements[0].color = (0.47, 0.47, 0.47, 1.0)
    detail_ramp.color_ramp.elements[1].position = 0.58
    detail_ramp.color_ramp.elements[1].color = (0.53, 0.53, 0.53, 1.0)

    bump.inputs[0].default_value = 0.08
    bump.inputs[1].default_value = 0.010
    micro_bump.inputs[0].default_value = 0.03
    micro_bump.inputs[1].default_value = 0.0012

    tint.outputs[0].default_value = (0.80, 0.81, 0.83, 1.0)

    set_socket_value(bsdf, ("Metallic",), 1.0)
    set_socket_value(bsdf, ("Roughness",), 0.16)
    set_socket_value(bsdf, ("Base Color",), (0.80, 0.81, 0.83, 1.0))
    set_socket_value(bsdf, ("Anisotropic",), clamp(0.72 * ALUMINUM_CONTRAST, 0.45, 0.95))
    set_socket_value(bsdf, ("Anisotropic Rotation",), 0.06)
    set_socket_value(bsdf, ("Specular IOR Level", "Specular"), 0.58)
    set_socket_value(bsdf, ("Coat Weight", "Clearcoat"), 0.02)
    set_socket_value(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.05)

    links.new(texcoord.outputs["Object"], mapping.inputs[0])
    links.new(mapping.outputs["Vector"], wave.inputs[0])
    links.new(mapping.outputs["Vector"], noise.inputs[0])
    links.new(mapping.outputs["Vector"], detail_noise.inputs[0])
    links.new(wave.outputs["Color"], blend.inputs[1])
    links.new(noise.outputs["Fac"], blend.inputs[2])
    links.new(blend.outputs["Color"], contrast.inputs[0])
    links.new(contrast.outputs["Color"], roughness_ramp.inputs["Fac"])
    links.new(detail_noise.outputs["Fac"], detail_ramp.inputs["Fac"])
    links.new(roughness_ramp.outputs["Color"], bump.inputs[2])
    links.new(detail_ramp.outputs["Color"], micro_bump.inputs[2])
    links.new(bump.outputs["Normal"], micro_bump.inputs["Normal"])
    links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    link_if_possible(nt, roughness_ramp.outputs["Color"], socket(bsdf, "Roughness"))
    link_if_possible(nt, micro_bump.outputs["Normal"], socket(bsdf, "Normal"))
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    return mat



def make_black_satin_plastic_material(name):
    """Deep black powder-printed plastic with restrained satin specular and micro porosity."""
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
    primary_noise = nodes.new("ShaderNodeTexNoise")
    pore_noise = nodes.new("ShaderNodeTexNoise")
    musgrave = nodes.new("ShaderNodeTexMusgrave")
    rough_mix = nodes.new("ShaderNodeMixRGB")
    rough_ramp = nodes.new("ShaderNodeValToRGB")
    pore_ramp = nodes.new("ShaderNodeValToRGB")
    color_mix = nodes.new("ShaderNodeMixRGB")
    contrast = nodes.new("ShaderNodeBrightContrast")
    dark_rgb = nodes.new("ShaderNodeRGB")
    edge_rgb = nodes.new("ShaderNodeRGB")
    bump = nodes.new("ShaderNodeBump")
    pore_bump = nodes.new("ShaderNodeBump")

    output.location = (980, 40)
    bsdf.location = (680, 40)
    texcoord.location = (-980, 0)
    mapping.location = (-760, 0)
    primary_noise.location = (-560, 180)
    musgrave.location = (-560, -10)
    pore_noise.location = (-560, -220)
    rough_mix.location = (-300, 100)
    contrast.location = (-80, 100)
    rough_ramp.location = (150, 110)
    pore_ramp.location = (-280, -220)
    bump.location = (180, -100)
    pore_bump.location = (400, -120)
    dark_rgb.location = (-80, 320)
    edge_rgb.location = (-80, 240)
    color_mix.location = (160, 250)

    mapping.inputs[4].default_value = (11.0, 11.0, 11.0)

    primary_noise.inputs[2].default_value = 8.0
    primary_noise.inputs[3].default_value = 2.0
    primary_noise.inputs[4].default_value = 0.5

    if hasattr(musgrave, "musgrave_type"):
        musgrave.musgrave_type = "RIDGED_MULTIFRACTAL"
    musgrave.inputs[2].default_value = 30.0
    musgrave.inputs[3].default_value = 6.0
    musgrave.inputs[4].default_value = 0.42

    pore_noise.inputs[2].default_value = 220.0
    pore_noise.inputs[3].default_value = 2.0
    pore_noise.inputs[4].default_value = 0.25

    rough_mix.blend_type = "SOFT_LIGHT"
    rough_mix.inputs[0].default_value = 0.58

    contrast.inputs[1].default_value = -0.03
    contrast.inputs[2].default_value = 0.25

    rough_ramp.color_ramp.elements[0].position = 0.30
    rough_ramp.color_ramp.elements[0].color = (0.40, 0.40, 0.40, 1.0)
    rough_ramp.color_ramp.elements[1].position = 0.84
    rough_ramp.color_ramp.elements[1].color = (0.62, 0.62, 0.62, 1.0)

    pore_ramp.color_ramp.elements[0].position = 0.44
    pore_ramp.color_ramp.elements[0].color = (0.49, 0.49, 0.49, 1.0)
    pore_ramp.color_ramp.elements[1].position = 0.58
    pore_ramp.color_ramp.elements[1].color = (0.51, 0.51, 0.51, 1.0)

    bump.inputs[0].default_value = 0.05
    bump.inputs[1].default_value = 0.0010
    pore_bump.inputs[0].default_value = 0.015
    pore_bump.inputs[1].default_value = 0.00028

    darkness = clamp(BLACK_PLASTIC_DARKNESS, 0.65, 1.25)
    dark_base = 0.018 / darkness
    edge_base = 0.038 / max(0.84, darkness)
    dark_rgb.outputs[0].default_value = (dark_base, dark_base, dark_base * 1.05, 1.0)
    edge_rgb.outputs[0].default_value = (edge_base, edge_base, edge_base * 1.05, 1.0)

    color_mix.blend_type = "MIX"
    color_mix.inputs[0].default_value = 0.22

    set_socket_value(bsdf, ("Metallic",), 0.0)
    set_socket_value(bsdf, ("Base Color",), (dark_base, dark_base, dark_base * 1.05, 1.0))
    set_socket_value(bsdf, ("Roughness",), 0.52)
    set_socket_value(bsdf, ("IOR",), 1.46)
    set_socket_value(bsdf, ("Specular IOR Level", "Specular"), 0.30)
    set_socket_value(bsdf, ("Coat Weight", "Clearcoat"), 0.015)
    set_socket_value(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.20)
    set_socket_value(bsdf, ("Sheen Weight", "Sheen"), 0.02)
    set_socket_value(bsdf, ("Sheen Roughness",), 0.65)

    links.new(texcoord.outputs["Object"], mapping.inputs[0])
    links.new(mapping.outputs["Vector"], primary_noise.inputs[0])
    links.new(mapping.outputs["Vector"], musgrave.inputs[0])
    links.new(mapping.outputs["Vector"], pore_noise.inputs[0])
    links.new(primary_noise.outputs["Fac"], rough_mix.inputs[1])
    links.new(musgrave.outputs["Fac"], rough_mix.inputs[2])
    links.new(rough_mix.outputs["Color"], contrast.inputs[0])
    links.new(contrast.outputs["Color"], rough_ramp.inputs["Fac"])
    links.new(pore_noise.outputs["Fac"], pore_ramp.inputs["Fac"])
    links.new(rough_ramp.outputs["Color"], bump.inputs[2])
    links.new(pore_ramp.outputs["Color"], pore_bump.inputs[2])
    links.new(bump.outputs["Normal"], pore_bump.inputs["Normal"])
    links.new(dark_rgb.outputs["Color"], color_mix.inputs[1])
    links.new(edge_rgb.outputs["Color"], color_mix.inputs[2])
    links.new(musgrave.outputs["Fac"], color_mix.inputs[0])
    links.new(color_mix.outputs["Color"], bsdf.inputs["Base Color"])
    link_if_possible(nt, rough_ramp.outputs["Color"], socket(bsdf, "Roughness"))
    link_if_possible(nt, pore_bump.outputs["Normal"], socket(bsdf, "Normal"))
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    return mat



def make_reflection_card_material(name, color=(1.0, 1.0, 1.0, 1.0), strength=3.0):
    """Emission plane that is invisible to the camera but still shows up in glossy reflections."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    clear_node_tree(nt)

    nodes = nt.nodes
    links = nt.links

    output = nodes.new("ShaderNodeOutputMaterial")
    mix = nodes.new("ShaderNodeMixShader")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    emission = nodes.new("ShaderNodeEmission")
    light_path = nodes.new("ShaderNodeLightPath")

    output.location = (520, 20)
    mix.location = (260, 20)
    transparent.location = (20, 120)
    emission.location = (20, -60)
    light_path.location = (-210, 20)

    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength

    links.new(light_path.outputs["Is Camera Ray"], mix.inputs[0])
    links.new(transparent.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], output.inputs["Surface"])

    return mat



def make_reflection_floor_material(name):
    """Dark glossy floor patch that fades out to transparent away from the product."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    nt = mat.node_tree
    clear_node_tree(nt)

    nodes = nt.nodes
    links = nt.links

    output = nodes.new("ShaderNodeOutputMaterial")
    mix_shader = nodes.new("ShaderNodeMixShader")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    texcoord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    gradient = nodes.new("ShaderNodeTexGradient")
    ramp = nodes.new("ShaderNodeValToRGB")
    noise = nodes.new("ShaderNodeTexNoise")
    mix_rgb = nodes.new("ShaderNodeMixRGB")
    rough_ramp = nodes.new("ShaderNodeValToRGB")

    output.location = (920, 20)
    mix_shader.location = (680, 20)
    transparent.location = (430, 150)
    bsdf.location = (430, -40)
    texcoord.location = (-760, 40)
    mapping.location = (-540, 40)
    gradient.location = (-320, 120)
    ramp.location = (-80, 120)
    noise.location = (-320, -130)
    mix_rgb.location = (150, -90)
    rough_ramp.location = (150, 80)

    gradient.gradient_type = "SPHERICAL"
    mapping.inputs[1].default_value = (-0.5, -0.5, 0.0)
    mapping.inputs[4].default_value = (0.65, 1.55, 1.0)

    floor_strength = clamp(REFLECTION_FLOOR_STRENGTH, 0.0, 1.0)
    ramp.color_ramp.elements[0].position = 0.12
    ramp.color_ramp.elements[0].color = (floor_strength, floor_strength, floor_strength, 1.0)
    ramp.color_ramp.elements[1].position = 0.55
    ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)

    noise.inputs[2].default_value = 70.0
    noise.inputs[3].default_value = 2.0
    noise.inputs[4].default_value = 0.12

    mix_rgb.blend_type = "MULTIPLY"
    mix_rgb.inputs[0].default_value = 0.25

    rough_ramp.color_ramp.elements[0].position = 0.28
    rough_ramp.color_ramp.elements[0].color = (0.10, 0.10, 0.10, 1.0)
    rough_ramp.color_ramp.elements[1].position = 0.72
    rough_ramp.color_ramp.elements[1].color = (0.18, 0.18, 0.18, 1.0)

    set_socket_value(bsdf, ("Base Color",), (0.003, 0.003, 0.003, 1.0))
    set_socket_value(bsdf, ("Metallic",), 0.0)
    set_socket_value(bsdf, ("Roughness",), 0.14)
    set_socket_value(bsdf, ("Specular IOR Level", "Specular"), 0.46)

    links.new(texcoord.outputs["Generated"], mapping.inputs[0])
    links.new(mapping.outputs["Vector"], gradient.inputs[0])
    links.new(mapping.outputs["Vector"], noise.inputs[0])
    links.new(gradient.outputs["Fac"], ramp.inputs["Fac"])
    links.new(noise.outputs["Fac"], mix_rgb.inputs[1])
    links.new(ramp.outputs["Color"], mix_rgb.inputs[2])
    links.new(mix_rgb.outputs["Color"], rough_ramp.inputs["Fac"])
    link_if_possible(nt, rough_ramp.outputs["Color"], socket(bsdf, "Roughness"))
    links.new(ramp.outputs["Color"], mix_shader.inputs[0])
    links.new(transparent.outputs["BSDF"], mix_shader.inputs[1])
    links.new(bsdf.outputs["BSDF"], mix_shader.inputs[2])
    links.new(mix_shader.outputs["Shader"], output.inputs["Surface"])

    return mat



def build_materials():
    return {
        "brushed_aluminum": make_brushed_aluminum_material("MAT_BrushedAluminum"),
        "black_satin_plastic": make_black_satin_plastic_material("MAT_BlackSatinPlastic"),
        "reflection_floor": make_reflection_floor_material("MAT_ReflectionFloor"),
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
    """Keep the camera background black while giving glossy rays richer studio-like fill."""
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("StudioWorld")

    world = scene.world
    world.use_nodes = True
    nt = world.node_tree
    clear_node_tree(nt)

    nodes = nt.nodes
    links = nt.links

    output = nodes.new("ShaderNodeOutputWorld")
    bg_camera = nodes.new("ShaderNodeBackground")
    bg_base = nodes.new("ShaderNodeBackground")
    bg_gloss = nodes.new("ShaderNodeBackground")
    mix_gloss = nodes.new("ShaderNodeMixShader")
    mix_camera = nodes.new("ShaderNodeMixShader")
    light_path = nodes.new("ShaderNodeLightPath")

    output.location = (760, 40)
    mix_camera.location = (520, 40)
    mix_gloss.location = (270, -50)
    bg_camera.location = (30, 190)
    bg_base.location = (30, 0)
    bg_gloss.location = (30, -190)
    light_path.location = (-200, 60)

    bg_camera.inputs["Color"].default_value = BACKGROUND_COLOR
    bg_camera.inputs["Strength"].default_value = 1.0

    if BACKGROUND_MODE == "PURE_BLACK":
        base_color = (0.0, 0.0, 0.0, 1.0)
        gloss_color = (0.0, 0.0, 0.0, 1.0)
        base_strength = 0.0
        gloss_strength = 0.0
    else:
        # Non-camera rays get a dim cool fill so metals do not die in pure black.
        base_color = (0.012, 0.0125, 0.0145, 1.0)
        gloss_color = (0.032, 0.034, 0.040, 1.0)
        base_strength = 0.18 * STUDIO_REFLECTION_INTENSITY
        gloss_strength = 0.55 * STUDIO_REFLECTION_INTENSITY

    bg_base.inputs["Color"].default_value = base_color
    bg_base.inputs["Strength"].default_value = base_strength
    bg_gloss.inputs["Color"].default_value = gloss_color
    bg_gloss.inputs["Strength"].default_value = gloss_strength

    links.new(light_path.outputs["Is Glossy Ray"], mix_gloss.inputs[0])
    links.new(bg_base.outputs["Background"], mix_gloss.inputs[1])
    links.new(bg_gloss.outputs["Background"], mix_gloss.inputs[2])
    links.new(light_path.outputs["Is Camera Ray"], mix_camera.inputs[0])
    links.new(bg_camera.outputs["Background"], mix_camera.inputs[1])
    links.new(mix_gloss.outputs["Shader"], mix_camera.inputs[2])
    links.new(mix_camera.outputs["Shader"], output.inputs["Surface"])

    print("  [World] Camera-black studio world configured")



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



def add_reflection_card(name, center, target, size_x, size_y, emission_strength, color=(1.0, 1.0, 1.0, 1.0)):
    """Large hidden emissive planes emulate bright HDRI panels in actual Cycles renders."""
    bpy.ops.mesh.primitive_plane_add(location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (size_x * 0.5, size_y * 0.5, 1.0)
    obj.rotation_euler = look_at_rotation(obj.location, target)

    mat = make_reflection_card_material(f"MAT_{name.replace(' ', '_')}", color=color, strength=emission_strength)
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    # The card should not render directly to camera or cast distracting shadows.
    set_object_ray_visibility(obj, camera=False, diffuse=False, glossy=True, transmission=False, shadow=False, scatter=False)
    if hasattr(obj, "hide_render"):
        obj.hide_render = False

    return obj



def add_reflection_floor(bounds, materials):
    if REFLECTION_FLOOR_STRENGTH <= 0.0:
        return None

    center, size, min_corner, max_corner = bounds
    span = max(size.x, size.y, size.z, 0.08)
    floor_z = min_corner.z - 0.0004

    bpy.ops.mesh.primitive_plane_add(location=(center.x, center.y, floor_z))
    floor = bpy.context.object
    floor.name = "ReflectionFloor"
    floor.scale = (span * 1.75, span * 1.35, 1.0)
    floor.data.materials.clear()
    floor.data.materials.append(materials["reflection_floor"])

    # Keep the floor elegant and minimal while still allowing the contact patch to render.
    set_object_ray_visibility(floor, diffuse=True, glossy=True, shadow=True)
    return floor



def setup_lighting(bounds):
    """Hybrid studio setup: controlled area lights + glossy-only reflection cards."""
    center, size, min_corner, max_corner = bounds
    setup_world()

    span = max(size.x, size.y, size.z, 0.08)
    cx, cy, cz = center.x, center.y, center.z
    z_top = max_corner.z
    z_low = min_corner.z

    quality_scale = 0.86 if PREVIEW_MODE else 1.0
    key_energy = 2100 * quality_scale
    fill_energy = 320 * quality_scale
    rim_energy = 1800 * quality_scale
    kicker_energy = 900 * quality_scale
    top_energy = 750 * quality_scale

    add_area_light(
        "Key Softbox",
        (cx + span * 1.35, cy - span * 1.90, z_top + span * 0.82),
        (math.radians(62.0), 0.0, math.radians(-33.0)),
        energy=key_energy,
        size_x=span * 1.18,
        size_y=span * 0.62,
        color=(1.0, 0.985, 0.965),
    )
    add_area_light(
        "Negative Fill Side",
        (cx - span * 1.95, cy - span * 0.35, cz + span * 0.28),
        (math.radians(85.0), 0.0, math.radians(58.0)),
        energy=fill_energy,
        size_x=span * 1.55,
        size_y=span * 0.90,
        color=(0.86, 0.90, 1.0),
    )
    add_area_light(
        "Rear Rim Strip",
        (cx + span * 0.20, cy + span * 1.95, z_top + span * 0.54),
        (math.radians(-68.0), 0.0, math.radians(2.0)),
        energy=rim_energy,
        size_x=span * 0.30,
        size_y=span * 1.85,
        color=(1.0, 1.0, 1.0),
    )
    add_area_light(
        "Lower Kicker",
        (cx - span * 0.22, cy - span * 1.15, z_low + span * 0.12),
        (math.radians(104.0), 0.0, math.radians(4.0)),
        energy=kicker_energy,
        size_x=span * 0.62,
        size_y=span * 0.22,
        color=(0.92, 0.96, 1.0),
        spread=math.radians(100.0),
    )
    add_area_light(
        "Top Accent",
        (cx + span * 0.10, cy - span * 0.15, z_top + span * 1.55),
        (math.radians(180.0), 0.0, 0.0),
        energy=top_energy,
        size_x=span * 0.45,
        size_y=span * 1.25,
        color=(1.0, 0.995, 0.985),
        spread=math.radians(90.0),
    )

    # Reflection cards emulate a premium HDRI without polluting the camera background.
    card_strength = STUDIO_REFLECTION_INTENSITY * (1.55 if PREVIEW_MODE else 1.85)
    add_reflection_card(
        "Card_Key_Right",
        center + Vector((span * 1.45, -span * 1.30, span * 0.35)),
        center + Vector((0.0, 0.0, span * 0.08)),
        size_x=span * 1.55,
        size_y=span * 1.05,
        emission_strength=card_strength * 2.2,
        color=(1.0, 0.995, 0.985, 1.0),
    )
    add_reflection_card(
        "Card_Fill_Left",
        center + Vector((-span * 1.50, -span * 0.55, span * 0.25)),
        center,
        size_x=span * 1.90,
        size_y=span * 1.20,
        emission_strength=card_strength * 1.15,
        color=(0.90, 0.94, 1.0, 1.0),
    )
    add_reflection_card(
        "Card_Overhead",
        center + Vector((0.0, -span * 0.10, span * 1.80)),
        center + Vector((0.0, 0.0, span * 0.12)),
        size_x=span * 0.85,
        size_y=span * 2.10,
        emission_strength=card_strength * 1.35,
        color=(1.0, 1.0, 1.0, 1.0),
    )
    add_reflection_card(
        "Card_Rear_Strip",
        center + Vector((span * 0.10, span * 1.75, span * 0.55)),
        center + Vector((0.0, 0.0, span * 0.10)),
        size_x=span * 0.35,
        size_y=span * 2.20,
        emission_strength=card_strength * 1.45,
        color=(1.0, 1.0, 1.0, 1.0),
    )

    print(f"  [Light] Hybrid studio setup created for span={span:.4f}m")



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

    # Refined three-quarter framing with slightly more vertical presence for a premium catalog feel.
    look_at = Vector(
        (
            center.x - size.x * 0.02,
            center.y + size.y * 0.015,
            center.z + size.z * 0.055,
        )
    )
    cam_offset = Vector((-span * 1.55, -span * 2.55, span * 0.88))
    cam_pos = look_at + cam_offset

    bpy.ops.object.camera_add(location=cam_pos)
    cam = bpy.context.object
    cam.name = "PitotCamera"
    cam.rotation_euler = look_at_rotation(cam_pos, look_at)
    cam.data.lens = 88 if PREVIEW_MODE else 100
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.001
    cam.data.clip_end = 1000
    cam.data.dof.use_dof = False

    scene = bpy.context.scene
    scene.camera = cam

    margin = 1.20
    horizontal_span = max(size.x, size.y) * margin
    vertical_span = size.z * margin
    lens_factor = max(horizontal_span / 2.0, vertical_span / 1.10)
    if lens_factor > 0:
        desired_distance = max(cam_offset.length, lens_factor * 4.1)
        view_dir = (cam_pos - look_at).normalized()
        cam.location = look_at + view_dir * desired_distance
        cam.rotation_euler = look_at_rotation(cam.location, look_at)

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
    scene.cycles.preview_samples = min(RENDER_SAMPLES, 96)
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 10
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 8
    scene.cycles.transmission_bounces = 4
    scene.cycles.transparent_max_bounces = 8
    scene.cycles.filter_width = 0.65
    if hasattr(scene.cycles, "blur_glossy"):
        scene.cycles.blur_glossy = 0.0
    if hasattr(scene.cycles, "sample_clamp_direct"):
        scene.cycles.sample_clamp_direct = 0.0
    if hasattr(scene.cycles, "sample_clamp_indirect"):
        scene.cycles.sample_clamp_indirect = 2.0 if PREVIEW_MODE else 1.5

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

    chosen_transform = None
    for transform in ("AgX", "Filmic", "Standard"):
        try:
            view_settings.view_transform = transform
            chosen_transform = transform
            print(f"  [CM] View Transform: {transform}")
            break
        except Exception:
            continue

    preferred_looks = {
        "AgX": ("AgX - High Contrast", "AgX - Medium High Contrast", "AgX - Base Contrast", "None"),
        "Filmic": ("Very High Contrast", "High Contrast", "Medium High Contrast", "None"),
        None: ("None",),
    }
    for look in preferred_looks.get(chosen_transform, ("None",)):
        try:
            view_settings.look = look
            print(f"  [CM] Look: {look}")
            break
        except Exception:
            continue

    # Slight negative exposure preserves the premium dark look and keeps the black polymer deep.
    view_settings.exposure = -0.35 if chosen_transform == "AgX" else -0.20
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

    setup_lighting(bounds)
    add_reflection_floor(bounds, materials)
    setup_camera(bounds)
    setup_render(render_out)

    print("\n" + "=" * 60)
    print("  Rendering...")
    print("=" * 60 + "\n")
    bpy.ops.render.render(write_still=True)
    print(f"\n[DONE] -> {render_out}")


main()

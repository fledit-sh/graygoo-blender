"""
Pitot Tube Studio Rendering Script
=================================
UBIQ Aerospace – ADS Pitot Tube (02000)

Blender-5-freundliche Produktvisualisierung mit Exploded View.

SETUP:
  1. Script in Blender 5 im Scripting-Tab laden
  2. Optional MANUAL_PARTS_DIR unten setzen
  3. Alt+P drücken
  4. System Console öffnen, um die Logs zu sehen
"""

import bpy
import math
import os
from mathutils import Vector


# ══════════════════════════════════════════════════════════════
#  ▶▶ EINSTELLUNGEN ◀◀
# ══════════════════════════════════════════════════════════════

# Leer lassen für automatische Pfaderkennung relativ zum Script/.blend.
MANUAL_PARTS_DIR = ""

PREVIEW_MODE = True
USE_EXPLODED_VIEW = True
EXPLODE_AXIS = "X"
EXPLODE_GAP = 0.028  # Meter nach STL-Import (global_scale=0.001)

BACKGROUND_COLOR = (0.012, 0.012, 0.014, 1.0)
GROUND_COLOR = (0.018, 0.018, 0.020, 1.0)


if PREVIEW_MODE:
    RENDER_WIDTH, RENDER_HEIGHT, RENDER_SAMPLES, OUTPUT_SUFFIX = 1280, 720, 48, "_preview"
else:
    RENDER_WIDTH, RENDER_HEIGHT, RENDER_SAMPLES, OUTPUT_SUFFIX = 2560, 1440, 320, ""


PARTS = [
    ("00_total_pressure_port.stl", "aluminum_dark", "Total Pressure Port"),
    ("01_main_housing.stl", "black_satin", "Pitot Tube Cover"),
    ("02_base_plate.stl", "black_satin", "Pitot Tube Base"),
    ("03_static_port.stl", "aluminum", "Static Ports"),
    ("04_fitting.stl", "aluminum", "Port Fitting"),
]


# ── Pfad-Ermittlung ──────────────────────────────────────────

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


# ── Utility ──────────────────────────────────────────────────

def socket(node, *names):
    for name in names:
        if name in node.inputs:
            return node.inputs[name]
    return None


def clear_node_tree(node_tree):
    for node in list(node_tree.nodes):
        node_tree.nodes.remove(node)


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


# ── Materialien ──────────────────────────────────────────────

def make_principled_material(
    name,
    base_color,
    metallic,
    roughness,
    coat=0.0,
    coat_roughness=0.03,
    specular_ior=1.5,
):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    clear_node_tree(nt)

    output = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")

    output.location = (320, 0)
    bsdf.location = (0, 0)

    socket(bsdf, "Base Color").default_value = base_color
    socket(bsdf, "Metallic").default_value = metallic
    socket(bsdf, "Roughness").default_value = roughness

    coat_socket = socket(bsdf, "Coat Weight", "Clearcoat")
    if coat_socket:
        coat_socket.default_value = coat

    coat_roughness_socket = socket(bsdf, "Coat Roughness", "Clearcoat Roughness")
    if coat_roughness_socket:
        coat_roughness_socket.default_value = coat_roughness

    specular_socket = socket(bsdf, "Specular IOR Level", "Specular")
    if specular_socket:
        specular_socket.default_value = specular_ior

    nt.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def build_materials():
    return {
        "aluminum": make_principled_material(
            "MAT_Aluminum",
            base_color=(0.79, 0.80, 0.82, 1.0),
            metallic=1.0,
            roughness=0.14,
            coat=0.08,
            coat_roughness=0.02,
        ),
        "aluminum_dark": make_principled_material(
            "MAT_AluminumDark",
            base_color=(0.63, 0.64, 0.67, 1.0),
            metallic=1.0,
            roughness=0.18,
            coat=0.06,
            coat_roughness=0.04,
        ),
        "black_satin": make_principled_material(
            "MAT_BlackSatin",
            base_color=(0.018, 0.018, 0.020, 1.0),
            metallic=0.02,
            roughness=0.42,
            coat=0.18,
            coat_roughness=0.12,
            specular_ior=1.3,
        ),
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
            print(f"    [WARN] STL-Import-Operator fehlgeschlagen: {exc}")

    print(f"    [FEHLER] STL-Import fehlgeschlagen: {filepath}")
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


# ── Szene ────────────────────────────────────────────────────

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
    )
    for blocks in datablocks:
        for block in list(blocks):
            if block.users == 0:
                blocks.remove(block)


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

    output.location = (240, 0)
    background.location = (0, 0)

    background.inputs["Color"].default_value = BACKGROUND_COLOR
    background.inputs["Strength"].default_value = 0.9
    nt.links.new(background.outputs["Background"], output.inputs["Surface"])

    print(f"  [World] Hintergrund gesetzt: {BACKGROUND_COLOR}")


def add_area_light(name, location, rotation, energy, size, color):
    bpy.ops.object.light_add(type="AREA", location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.energy = energy
    obj.data.size = size
    obj.data.color = color
    return obj


def setup_lighting(cx, cy, cz, span):
    setup_world()
    d = max(span, 0.08)

    add_area_light(
        "Key Light",
        (cx + d * 1.20, cy - d * 1.25, cz + d * 0.95),
        (math.radians(58), 0.0, math.radians(-34)),
        energy=3200 if PREVIEW_MODE else 4500,
        size=d * 0.62,
        color=(1.0, 0.975, 0.94),
    )
    add_area_light(
        "Fill Light",
        (cx - d * 1.35, cy - d * 0.55, cz + d * 0.32),
        (math.radians(84), 0.0, math.radians(58)),
        energy=600 if PREVIEW_MODE else 900,
        size=d * 1.20,
        color=(0.82, 0.89, 1.0),
    )
    add_area_light(
        "Rim Light",
        (cx + d * 0.20, cy + d * 1.35, cz + d * 1.12),
        (math.radians(-54), 0.0, math.radians(8)),
        energy=1400 if PREVIEW_MODE else 1800,
        size=d * 0.55,
        color=(1.0, 1.0, 1.0),
    )
    print(f"  [Light] Studio-Lichter erstellt, span={span:.4f}m")


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
    look_at = Vector(
        (
            center.x - size.x * 0.08,
            center.y + size.y * 0.02,
            center.z + size.z * 0.03,
        )
    )
    distance = span * 3.35
    cam_pos = look_at + Vector((-distance * 0.55, -distance * 1.00, distance * 0.36))

    bpy.ops.object.camera_add(location=cam_pos)
    cam = bpy.context.object
    cam.name = "PitotCamera"
    cam.rotation_euler = (look_at - cam_pos).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 72 if PREVIEW_MODE else 85
    cam.data.clip_start = 0.001
    cam.data.clip_end = 1000

    scene = bpy.context.scene
    scene.camera = cam

    ground_size = max(size.x, size.y) * 2.6 + 0.25
    ground_z = min_corner.z - max(size.z * 0.05, 0.003)
    bpy.ops.mesh.primitive_plane_add(size=ground_size, location=(center.x, center.y, ground_z))
    ground = bpy.context.object
    ground.name = "StudioGround"
    ground.data.materials.append(
        make_principled_material(
            "MAT_Ground",
            base_color=GROUND_COLOR,
            metallic=0.0,
            roughness=0.25,
            coat=0.05,
            coat_roughness=0.08,
            specular_ior=1.4,
        )
    )

    print(f"  [Camera] lens={cam.data.lens}mm dist={distance:.4f}")
    print(f"  [Ground] size={ground_size:.4f} z={ground_z:.4f}")


# ── Render-Setup ─────────────────────────────────────────────

def setup_cycles_devices(scene):
    preferences = bpy.context.preferences
    cycles_addon = preferences.addons.get("cycles")
    if cycles_addon is None:
        scene.cycles.device = "CPU"
        print("  [GPU] Cycles-Addon nicht gefunden -> CPU")
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
            print(f"  [GPU] Verwende {device_type}")
            return
        except Exception as exc:
            print(f"  [GPU] {device_type} nicht nutzbar: {exc}")

    scene.cycles.device = "CPU"
    print("  [GPU] Keine GPU verfügbar -> CPU")


def setup_render(render_out):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = RENDER_WIDTH
    scene.render.resolution_y = RENDER_HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.filepath = render_out
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    scene.cycles.samples = RENDER_SAMPLES
    scene.cycles.preview_samples = min(RENDER_SAMPLES, 64)
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 12
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 6
    scene.cycles.transmission_bounces = 8
    scene.cycles.transparent_max_bounces = 8

    if PREVIEW_MODE:
        scene.cycles.device = "CPU"
        print("  [Render] Preview -> CPU für reproduzierbares Test-Setup")
    else:
        setup_cycles_devices(scene)

    view_settings = scene.view_settings
    for transform in ("AgX", "Filmic", "Standard"):
        try:
            view_settings.view_transform = transform
            print(f"  [CM] View Transform: {transform}")
            break
        except Exception:
            continue

    for look in (
        "AgX - High Contrast",
        "AgX - Base Contrast",
        "High Contrast",
        "Medium High Contrast",
        "None",
    ):
        try:
            view_settings.look = look
            print(f"  [CM] Look: {look}")
            break
        except Exception:
            continue

    view_settings.exposure = -0.35
    view_settings.gamma = 1.0

    print(
        f"  [Render] {RENDER_WIDTH}x{RENDER_HEIGHT}, {RENDER_SAMPLES}spp -> {render_out}"
    )


# ── Hauptprogramm ────────────────────────────────────────────

def main():
    mode_label = "PREVIEW" if PREVIEW_MODE else "FINAL"
    print("\n" + "=" * 60)
    print(f"  PITOT TUBE – {mode_label}  ({RENDER_WIDTH}x{RENDER_HEIGHT}, {RENDER_SAMPLES}spp)")
    print("=" * 60)

    parts_dir = get_parts_dir()
    if not parts_dir:
        print(f"\n[FEHLER] parts_obj nicht gefunden. MANUAL_PARTS_DIR='{MANUAL_PARTS_DIR}'")
        return

    render_out = os.path.join(os.path.dirname(parts_dir), f"pitot_render{OUTPUT_SUFFIX}.png")
    print(f"  [Input]  {parts_dir}")
    print(f"  [Output] {render_out}")

    cleanup_scene()
    materials = build_materials()

    print("\nImportiere Teile...")
    objects = []
    for filename, material_key, label in PARTS:
        filepath = os.path.join(parts_dir, filename)
        if not os.path.exists(filepath):
            print(f"  [SKIP] {filename}")
            continue

        obj = import_stl(filepath)
        if obj is None:
            print(f"  [FEHLER] {filename}")
            continue

        obj.name = label
        smooth_object(obj)
        obj.data.materials.clear()
        obj.data.materials.append(materials[material_key])
        objects.append(obj)
        print(f"  [OK]   {label:<22} -> {material_key}")

    if not objects:
        print("\n[FEHLER] Keine Teile importiert.")
        return

    if USE_EXPLODED_VIEW and len(objects) > 1:
        print("\nExploded View...")
        layout_exploded(objects, axis=EXPLODE_AXIS, gap=EXPLODE_GAP)

    print("\nScene setup...")
    bounds = compute_bounds(objects)
    if bounds is None:
        print("[FEHLER] Bounding-Box konnte nicht bestimmt werden.")
        return

    center, size, _, _ = bounds
    setup_lighting(center.x, center.y, center.z, max(size.x, size.y, size.z))
    setup_camera(bounds)
    setup_render(render_out)

    print("\n" + "=" * 60)
    print("  Rendering...")
    print("=" * 60 + "\n")
    bpy.ops.render.render(write_still=True)
    print(f"\n[FERTIG] -> {render_out}")


main()

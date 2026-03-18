"""
Pitot Tube Studio Rendering Script
====================================
UBIQ Aerospace – ADS Pitot Tube (02000)

SETUP:
  1. MANUAL_PARTS_DIR unten anpassen
  2. PREVIEW_MODE = True  → schnelles Testbild (960x540, 24 Samples, ~30 Sek.)
     PREVIEW_MODE = False → finales Rendering (2560x1440, 256 Samples)
  3. In Blender: Scripting-Tab → Script laden → Alt+P
  4. System Console öffnen (Window → Toggle System Console) → Logs lesen!
"""

import bpy
import os
import math
from mathutils import Vector

# ══════════════════════════════════════════════════════════════
#  ▶▶ EINSTELLUNGEN ◀◀
# ══════════════════════════════════════════════════════════════

MANUAL_PARTS_DIR = r"C:\Users\Noel\PycharmProjects\graygoo-blender"

PREVIEW_MODE = True   # True = schnell testen  |  False = finales Rendering

# ══════════════════════════════════════════════════════════════

if PREVIEW_MODE:
    RENDER_WIDTH, RENDER_HEIGHT, RENDER_SAMPLES, OUTPUT_SUFFIX = 960, 540, 24, "_preview"
else:
    RENDER_WIDTH, RENDER_HEIGHT, RENDER_SAMPLES, OUTPUT_SUFFIX = 2560, 1440, 256, ""

PARTS = [
    ("00_total_pressure_port.stl", "aluminum",    "Total Pressure Port"),
    ("01_main_housing.stl",        "black_paint", "Pitot Tube Cover"),
    ("02_base_plate.stl",          "black_paint", "Pitot Tube Base"),
    ("03_static_port.stl",         "aluminum",    "Static Ports"),
    ("04_fitting.stl",             "aluminum",    "Port Fitting"),
]


# ── Pfad-Ermittlung ──────────────────────────────────────────

def get_parts_dir():
    if MANUAL_PARTS_DIR:
        c = os.path.join(MANUAL_PARTS_DIR, "parts_obj")
        if os.path.isdir(c):
            return c
        if os.path.isdir(MANUAL_PARTS_DIR):
            return MANUAL_PARTS_DIR
    try:
        c = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parts_obj")
        if os.path.isdir(c):
            return c
    except NameError:
        pass
    for text in bpy.data.texts:
        if text.filepath:
            c = os.path.join(os.path.dirname(bpy.path.abspath(text.filepath)), "parts_obj")
            if os.path.isdir(c):
                return c
    if bpy.data.filepath:
        c = os.path.join(os.path.dirname(bpy.data.filepath), "parts_obj")
        if os.path.isdir(c):
            return c
    return None


# ── Materialien ──────────────────────────────────────────────

def make_material(name, base_color, metallic, roughness, coat=0.0, coat_roughness=0.05):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out.location = (300, 0)
    bsdf.location = (0, 0)
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    for key in ("Coat Weight", "Clearcoat"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = coat
            break
    for key in ("Coat Roughness", "Clearcoat Roughness"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = coat_roughness
            break
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# ── Import ───────────────────────────────────────────────────

def import_stl(filepath):
    bpy.ops.object.select_all(action='DESELECT')
    for op in (
        lambda: bpy.ops.wm.stl_import(filepath=filepath, global_scale=0.001),
        lambda: bpy.ops.import_mesh.stl(filepath=filepath, global_scale=0.001),
    ):
        try:
            op()
            sel = bpy.context.selected_objects
            return sel[0] if sel else None
        except Exception:
            continue
    print(f"    STL-Import fehlgeschlagen: {filepath}")
    return None


# ── World: garantiert dunkel ─────────────────────────────────

def setup_world():
    """
    Modifiziert die bestehende aktive World direkt.
    Schwarz als Weltfarbe + geringe/intuitive Strength für sauberen schwarzen Background.
    """
    scene = bpy.context.scene

    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    w = scene.world
    w.use_nodes = True

    nt = w.node_tree

    bg_node = next((n for n in nt.nodes if n.type == 'BACKGROUND'), None)
    out_node = next((n for n in nt.nodes if n.type == 'OUTPUT_WORLD'), None)

    if bg_node is None or out_node is None:
        nt.nodes.clear()
        bg_node = nt.nodes.new("ShaderNodeBackground")
        out_node = nt.nodes.new("ShaderNodeOutputWorld")
        bg_node.location = (0, 0)
        out_node.location = (250, 0)
        nt.links.new(bg_node.outputs[0], out_node.inputs[0])

    # Schwarzer Hintergrund. Strength > 0 ist robuster als 0.0 in manchen Setups.
    bg_node.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
    bg_node.inputs[1].default_value = 1.0

    print(f"  [World] '{w.name}'  Strength={bg_node.inputs[1].default_value}  (schwarzer Hintergrund aktiv)")


# ── Beleuchtung ──────────────────────────────────────────────

def setup_lighting(cx=0.0, cy=0.0, cz=0.0, diag=0.3):
    """
    Positioniert Lichter relativ zur Modell-Bounding-Box.
    Funktioniert unabhängig von der Modellgröße.
    """
    setup_world()

    d = max(diag, 0.01)

    lights = [
        (
            "Key", 'AREA',
            (cx + d * 1.1, cy - d * 0.4, cz + d * 1.0),
            (math.radians(60), 0, math.radians(-55)),
            650, d * 0.4, (1.00, 0.96, 0.90),
        ),
        (
            "Fill", 'AREA',
            (cx - d * 0.6, cy - d * 0.5, cz + d * 0.3),
            (math.radians(18), 0, math.radians(55)),
            3, d * 1.5, (0.85, 0.90, 1.00),
        ),
        (
            "Rim", 'AREA',
            (cx - d * 0.1, cy + d * 1.0, cz + d * 1.0),
            (math.radians(-60), 0, math.radians(8)),
            80, d * 0.3, (1.00, 1.00, 1.00),
        ),
    ]
    for name, ltype, loc, rot, energy, size, color in lights:
        bpy.ops.object.light_add(type=ltype, location=loc)
        l = bpy.context.object
        l.name = f"Light_{name}"
        l.rotation_euler = rot
        l.data.energy = energy
        l.data.size = size
        l.data.color = color
        print(f"  [Light] {name}: {energy}W @ {loc}  size={size:.4f}")


# ── Kamera & Boden ───────────────────────────────────────────

def compute_bounds(objects):
    """Berechnet Bounding-Box aller importierten Objekte."""
    all_co = []
    for obj in objects:
        for v in obj.data.vertices:
            all_co.append(obj.matrix_world @ v.co)
    if not all_co:
        return None
    xs = [c.x for c in all_co]
    ys = [c.y for c in all_co]
    zs = [c.z for c in all_co]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    zmin, zmax = min(zs), max(zs)
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    cz = (zmin + zmax) / 2
    diag = math.sqrt((xmax - xmin) ** 2 + (ymax - ymin) ** 2 + (zmax - zmin) ** 2)
    print(f"  [Bounds] cx={cx:.4f} cy={cy:.4f} cz={cz:.4f}  diag={diag:.4f}m")
    return cx, cy, cz, diag, zmin


def setup_camera(cx, cy, cz, diag, zmin):
    dx = diag * 0.5
    dz = diag * 0.3
    look_at = Vector((cx - dx * 0.25, cy, cz - dz * 0.10))

    dist = diag * 2.5
    cam_pos = look_at + Vector((-dist * 0.42, -dist * 0.88, dist * 0.38))

    bpy.ops.object.camera_add(location=cam_pos)
    cam = bpy.context.object
    cam.name = "PitotCamera"
    cam.rotation_euler = (look_at - cam_pos).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 85
    bpy.context.scene.camera = cam
    print(f"  [Camera] dist={dist:.3f}  look_at={look_at[:]}")

    ground_size = max(diag * 20, 0.5)
    bpy.ops.mesh.primitive_plane_add(size=ground_size, location=(cx, cy, zmin - diag * 0.001))
    ground = bpy.context.object
    ground.name = "StudioGround"
    ground.data.materials.append(make_material(
        "MAT_Ground",
        base_color=(0.008, 0.008, 0.010, 1.0),
        metallic=0.0,
        roughness=0.08,
    ))
    print(f"  [Ground] size={ground_size:.4f}m @ z={zmin:.4f}")


# ── Render-Setup ─────────────────────────────────────────────

def setup_render(render_out):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = RENDER_WIDTH
    scene.render.resolution_y = RENDER_HEIGHT
    scene.render.filepath = render_out
    scene.render.image_settings.file_format = 'PNG'
    scene.cycles.samples = RENDER_SAMPLES
    scene.cycles.use_denoising = True

    # GPU
    if not PREVIEW_MODE:
        gpu_set = False
        for device_type in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
            try:
                cp = bpy.context.preferences.addons['cycles'].preferences
                cp.compute_device_type = device_type
                try:
                    cp.refresh_devices()
                except Exception:
                    cp.get_devices()
                for d in cp.devices:
                    d.use = True
                scene.cycles.device = 'GPU'
                print(f"  GPU: {device_type}")
                gpu_set = True
                break
            except Exception:
                continue
        if not gpu_set:
            scene.cycles.device = 'CPU'
    else:
        scene.cycles.device = 'CPU'

    # Kein Compositor-Zwang: schwarzer Hintergrund direkt über World.
    # Das vermeidet Fehler wie: AttributeError: 'Scene' object has no attribute 'node_tree'
    scene.render.film_transparent = False
    print("  [Render] Schwarzer Hintergrund über World konfiguriert (ohne Compositor)")

    cm = scene.view_settings

    try:
        vt_options = [i.identifier for i in cm.bl_rna.properties['view_transform'].enum_items]
        print(f"  [CM] View Transforms verfügbar: {vt_options}")
    except Exception:
        vt_options = []

    for vt in ('AgX', 'Filmic', 'Standard'):
        if not vt_options or vt in vt_options:
            try:
                cm.view_transform = vt
                print(f"  [CM] View Transform: {vt}")
                break
            except Exception:
                continue

    try:
        look_options = [i.identifier for i in cm.bl_rna.properties['look'].enum_items]
        print(f"  [CM] Looks verfügbar: {look_options}")
    except Exception:
        look_options = []

    for look in (
        'AgX - Very High Contrast', 'Very High Contrast',
        'AgX - High Contrast', 'High Contrast',
        'AgX - Base Contrast', 'Base Contrast', 'None'
    ):
        if not look_options or look in look_options:
            try:
                cm.look = look
                print(f"  [CM] Look: {look}")
                break
            except Exception:
                continue

    cm.exposure = -1.0
    cm.gamma = 1.0
    print(f"  [CM] Exposure={cm.exposure}  Gamma={cm.gamma}")
    print(f"  [CM] Aktiver Transform: {cm.view_transform}  Look: {cm.look}")


# ── Hauptprogramm ────────────────────────────────────────────

def main():
    mode_label = "PREVIEW" if PREVIEW_MODE else "FINAL"
    print("\n" + "=" * 55)
    print(f"  PITOT TUBE – {mode_label}  ({RENDER_WIDTH}x{RENDER_HEIGHT}, {RENDER_SAMPLES}spp)")
    print("=" * 55)

    parts_dir = get_parts_dir()
    if not parts_dir:
        print(f"\n[FEHLER] parts_obj nicht gefunden! MANUAL_PARTS_DIR='{MANUAL_PARTS_DIR}'")
        return

    render_out = os.path.join(os.path.dirname(parts_dir), f"pitot_render{OUTPUT_SUFFIX}.png")
    print(f"  STL   : {parts_dir}")
    print(f"  Output: {render_out}")

    # ── Szene komplett leeren ────────────────────────────────
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    for block in list(bpy.data.meshes):
        if block.users == 0:
            bpy.data.meshes.remove(block)

    for block in list(bpy.data.materials):
        if block.users == 0:
            bpy.data.materials.remove(block)

    # ── Materialien ─────────────────────────────────────────
    mat_alu = make_material(
        "MAT_Aluminum",
        base_color=(0.78, 0.78, 0.80, 1.0),
        metallic=1.0,
        roughness=0.12,
        coat=0.0,
    )
    mat_blk = make_material(
        "MAT_BlackPaint",
        base_color=(0.005, 0.005, 0.006, 1.0),
        metallic=0.0,
        roughness=0.95,
        coat=0.0,
        coat_roughness=1.0,
    )
    materials = {"aluminum": mat_alu, "black_paint": mat_blk}

    # ── STL-Import ──────────────────────────────────────────
    print("\nImportiere Teile...")
    objects = []
    for filename, mat_key, desc in PARTS:
        fp = os.path.join(parts_dir, filename)
        if not os.path.exists(fp):
            print(f"  [SKIP]   {filename}")
            continue
        obj = import_stl(fp)
        if not obj:
            print(f"  [FEHLER] {filename}")
            continue
        obj.name = desc
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_smooth()
        mat = materials[mat_key]
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        objects.append(obj)
        print(f"  [OK]  {desc:<28} → {mat_key}")

    if not objects:
        print("\n[FEHLER] Keine Teile importiert.")
        return

    print("\nScene setup...")
    bounds = compute_bounds(objects)
    if bounds:
        cx, cy, cz, diag, zmin = bounds
        setup_lighting(cx, cy, cz, diag)
        setup_camera(cx, cy, cz, diag, zmin)
    else:
        setup_lighting()
        print("  [WARN] Bounds konnten nicht berechnet werden – Standardbeleuchtung")
    setup_render(render_out)

    print(f"\n{'=' * 55}")
    print("  Rendering...")
    print(f"{'=' * 55}\n")
    bpy.ops.render.render(write_still=True)
    print(f"\n[FERTIG] → {render_out}")


main()

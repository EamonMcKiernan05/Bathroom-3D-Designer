"""Render 256px EEVEE thumbnails for every GLB in assets/models.

Run:  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background --python blender_thumbnails.py
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS = ROOT / "assets" / "models"
THUMBS = ROOT / "assets" / "thumbnails"
THUMBS.mkdir(parents=True, exist_ok=True)

SLUGS = sorted(p.stem for p in MODELS.glob("*.glb"))


def render_one(slug: str):
    path = str(MODELS / f"{slug}.glb")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not objs:
        print(f"[NO MESH] {slug}")
        return
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()

    obj = bpy.context.active_object
    # frame bounds
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 0.05)
    dist = size * 2.2

    # lights: sun key + fill (no falloff — reliable EEVEE lighting)
    world = bpy.data.worlds.new("ThumbWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
    bg.inputs[1].default_value = 0.6
    scene.world = world
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "SUN"))
    key.rotation_euler = (math.radians(50), 0, math.radians(-40))
    key.data.energy = 4.0
    bpy.context.collection.objects.link(key)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "SUN"))
    fill.rotation_euler = (math.radians(30), 0, math.radians(120))
    fill.data.energy = 1.5
    bpy.context.collection.objects.link(fill)
    rim = bpy.data.objects.new("Rim", bpy.data.lights.new("Rim", "SUN"))
    rim.rotation_euler = (math.radians(70), 0, math.radians(200))
    rim.data.energy = 0.8
    bpy.context.collection.objects.link(rim)

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.location = (cx + dist * 0.85, cy - dist * 0.85, cz + dist * 0.75)
    cam.rotation_euler = (1.07, 0, 0.72)
    cam.data.lens = 50
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    scene.render.filepath = str(THUMBS / f"{slug}.png")
    bpy.ops.render.render(write_still=True)
    print(f"[THUMB] {slug}")


for s in SLUGS:
    try:
        render_one(s)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[THUMB FAIL] {s}: {e}")

print(f"THUMBS_DONE {len(SLUGS)}")

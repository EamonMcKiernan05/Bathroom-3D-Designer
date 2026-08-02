"""Render 256px EEVEE thumbnails for every GLB in assets/models.
Fixed 3/4-view framing + light-grey world so product cards look clean.

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
    scene.render.image_settings.file_format = "PNG"

    # light grey world so white models read against a clean background
    world = bpy.data.worlds.new(f"W_{slug}")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.85, 0.85, 0.85, 1)
    bg.inputs[1].default_value = 1.0
    scene.world = world

    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not objs:
        print(f"[NO MESH] {slug}")
        return
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    obj = bpy.context.active_object

    # lights: 3 suns (no falloff — reliable)
    for i, (key, energy, rot) in enumerate([
        ("Key", 4.5, (math.radians(55), 0, math.radians(-50))),
        ("Fill", 2.0, (math.radians(30), 0, math.radians(120))),
        ("Rim", 1.2, (math.radians(75), 0, math.radians(210))),
    ]):
        L = bpy.data.objects.new(key, bpy.data.lights.new(key, "SUN"))
        L.rotation_euler = rot
        L.data.energy = energy
        scene.collection.objects.link(L)

    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    center = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))

    # camera basis from view direction
    dirv = Vector((1.0, -0.9, 0.75)).normalized()  # from camera toward object
    x_axis = dirv.cross(Vector((0, 0, 1)))
    if x_axis.length < 1e-6:
        x_axis = Vector((1, 0, 0))
    x_axis.normalize()
    y_axis = x_axis.cross(dirv)
    y_axis.normalize()

    # projected half-extent perpendicular to view (object_half_x / object_half_y)
    ohx = 0.0
    ohy = 0.0
    for c in bbox:
        rel = Vector(c) - center
        ohx = max(ohx, abs(rel.dot(x_axis)))
        ohy = max(ohy, abs(rel.dot(y_axis)))

    # fit distance so both extents fall inside the frustum (square sensor, sensor half-height 18mm)
    focal = 50.0
    tan_half = 18.0 / focal
    D = max(ohx, ohy) / tan_half * 1.2

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.location = center + dirv * D
    cam.data.lens = focal
    look = (center - cam.location).normalized()
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = Vector((0, 0, -1)).rotation_difference(look)
    scene.collection.objects.link(cam)
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

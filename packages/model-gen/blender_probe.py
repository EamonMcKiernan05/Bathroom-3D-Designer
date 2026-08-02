"""Probe GLB geometry: import a model, report per-object face counts + bbox, render a clean 512px PNG."""
import sys, math
from pathlib import Path
import bpy
from mathutils import Vector

MODELS = Path(r"C:/Users/Eamon/Desktop/bathroom-3d/assets/models")
OUT = Path(r"C:/Users/Eamon/Desktop/bathroom-3d/assets/qa")

def probe(slug):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 512
    sc.render.resolution_y = 512
    sc.render.image_settings.file_format = "PNG"
    # light grey world so white models read
    w = bpy.data.worlds.new("W")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.82,0.82,0.82,1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    sc.world = w
    bpy.ops.import_scene.gltf(filepath=str(MODELS / f"{slug}.glb"))
    objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.join()
        obj = bpy.context.active_object
    # camera: 3/4 view clearly showing front + side + top, full-fit framing
    for i, (key, energy, rot) in enumerate([
        ("Key", 4.5, (math.radians(55), 0, math.radians(-50))),
        ("Fill", 2.0, (math.radians(30), 0, math.radians(120))),
        ("Rim", 1.2, (math.radians(75), 0, math.radians(210))),
    ]):
        L = bpy.data.objects.new(key, bpy.data.lights.new(key, "SUN")); L.rotation_euler = rot; L.data.energy = energy
        sc.collection.objects.link(L)
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs=[v.x for v in bbox]; ys=[v.y for v in bbox]; zs=[v.z for v in bbox]
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
    w=max(xs)-min(xs); d=max(ys)-min(ys); h=max(zs)-min(zs)
    maxdim = max(w,d,h)
    cam = bpy.data.objects.new("C", bpy.data.cameras.new("C"))
    # place camera on a 3/4 sphere around center, radius proportional to size
    radius = maxdim * 1.6
    dirv = Vector((1.0, -0.9, 1.1)).normalized()
    cam.location = Vector((cx,cy,cz)) + dirv * radius
    cam.data.lens = 45
    # point camera at center
    look = (Vector((cx,cy,cz)) - cam.location).normalized()
    # rotation from a camera looking down -Z
    import math as _m
    cam.rotation_mode = 'QUATERNION'
    q = Vector((0,0,-1)).rotation_difference(look)
    cam.rotation_quaternion = q
    sc.collection.objects.link(cam); sc.camera=cam
    n_faces = len(obj.data.polygons) if objs else 0
    print(f"{slug}: objs={len(objs)} joined_faces={n_faces} size=({round(max(xs)-min(xs),1)},{round(max(ys)-min(ys),1)},{round(max(zs)-min(zs),1)})")
    sc.render.filepath = str(OUT / f"{slug}.png")
    bpy.ops.render.render(write_still=True)

args = sys.argv
if "--" in args:
    slugs = args[args.index("--") + 1:]
else:
    slugs = args[1:]
for s in slugs:
    probe(s)
print("DONE")

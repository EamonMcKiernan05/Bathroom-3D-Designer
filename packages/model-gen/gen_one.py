"""Generate one product's 3D model + thumbnail inside Blender (headless).

Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background --python gen_one.py -- --data <product.json>

Where <product.json> is:
  {
    "slug": "toilet",            # builder key (category -> slug mapping)
    "id": 1234,                  # products.id (used for output filename)
    "width_mm": 380, "height_mm": 780, "depth_mm": 660,
    "finish": "chrome"           # optional finish override
  }

Outputs:
  assets/models/model_<id>.glb
  assets/thumbnails/model_<id>.png
Prints MODEL_OK <id> on success.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import blender_lib  # noqa: E402

ROOT = HERE.parent.parent  # packages/model-gen/gen_one.py -> packages -> repo root
MODELS = ROOT / "assets" / "models"
THUMBS = ROOT / "assets" / "thumbnails"
MODELS.mkdir(parents=True, exist_ok=True)
THUMBS.mkdir(parents=True, exist_ok=True)


def _thumb(obj, out_path: str):
    """256px EEVEE 3/4-view thumbnail (same framing as blender_thumbnails.py)."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.image_settings.file_format = "PNG"

    world = bpy.data.worlds.new(f"W_{obj.name}")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.85, 0.85, 0.85, 1)
    bg.inputs[1].default_value = 1.0
    scene.world = world

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
    xs = [v.x for v in bbox]; ys = [v.y for v in bbox]; zs = [v.z for v in bbox]
    center = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    dirv = Vector((1.0, -0.9, 0.75)).normalized()
    x_axis = dirv.cross(Vector((0, 0, 1))).normalized()
    y_axis = x_axis.cross(dirv).normalized()
    ohx = max(abs((Vector(c) - center).dot(x_axis)) for c in bbox)
    ohy = max(abs((Vector(c) - center).dot(y_axis)) for c in bbox)
    focal = 50.0
    D = max(ohx, ohy) / (18.0 / focal) * 1.2
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.location = center + dirv * D
    cam.data.lens = focal
    look = (center - cam.location).normalized()
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = Vector((0, 0, -1)).rotation_difference(look)
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    data_path = None
    if args:
        if args[0] == "--data" and len(args) > 1:
            data_path = args[1]
        else:
            data_path = args[0]
    if not data_path:
        print("gen_one: no --data <product.json> given")
        sys.exit(2)

    data = json.loads(Path(data_path).read_text())
    slug = data["slug"]
    if slug not in blender_lib.BUILDERS:
        print(f"UNKNOWN_BUILD {slug}")

    out_stem = f"model_{data['id']}"
    glb_path = blender_lib.build_scaled(
        slug,
        data.get("width_mm"),
        data.get("height_mm"),
        data.get("depth_mm"),
        data.get("finish"),
        out_name=out_stem,
    )

    # render thumbnail from the in-scene joined object
    obj = bpy.context.view_layer.objects.active or bpy.context.selected_objects[0]
    _thumb(obj, str(THUMBS / f"{out_stem}.png"))

    n_polys = sum(len(m.data.polygons) for m in bpy.data.objects if m.type == "MESH" and m.data)
    print(f"MODEL_OK {data['id']} glb={glb_path} polys={n_polys}")


if __name__ == "__main__":
    main()
"""Check whether bath side-wall normals point outward (away from bbox center) or inward."""
import bpy
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="C:/Users/Eamon/Desktop/bathroom-3d/assets/models/bath.glb")
o = bpy.context.active_object
assert o.type == 'MESH'
# world centroid of all verts
wc = Vector((0,0,0))
mesh = o.data
for v in mesh.vertices:
    wc += o.matrix_world @ v.co
wc /= len(mesh.vertices)
outward=0; inward=0
for f in mesh.polygons:
    center = o.matrix_world @ f.center
    n = o.matrix_world.to_3x3() @ f.normal
    to_center = (center - wc).normalized()
    if n.dot(to_center) > 0: outward += 1
    elif abs(f.normal[2]) > 0.85: outward += 1  # horizontal caps: ignore
    else: inward += 1
print(f"faces={len(mesh.polygons)} outward_or_horiz={outward} inward_pointing={inward}")

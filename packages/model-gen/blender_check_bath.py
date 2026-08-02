"""Count bath faces by normal orientation: vertical (z≈0) vs horizontal (z≈±1)."""
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="C:/Users/Eamon/Desktop/bathroom-3d/assets/models/bath.glb")
p = bpy.context.active_object
print("num meshes:", len([o for o in bpy.data.objects if o.type=='MESH']))
total=0; side=0; horiz=0; other=0
for o in [o for o in bpy.data.objects if o.type=='MESH']:
    mesh = o.data
    for f in mesh.polygons:
        total+=1
        z=abs(f.normal[2])
        if z<0.3: side+=1
        elif z>0.85: horiz+=1
        else: other+=1
print(f"faces={total} side_walls(z<0.3)={side} horizontal(z>0.85)={horiz} other={other}")

"""Blender-side parametric model library. Executed inside Blender via the MCP addon's execute_code.

Convention (mm in Three.js, metres in Blender):
- Origin at BACK-BOTTOM-CENTER: local +Z = up, +X = right, front points toward Blender -Y.
  After Y-up GLB export, Blender -Y -> Three.js +Z, so models face +Z (into the room) at rotation 0.
- Back face sits at the wall: placement sets position on the wall line; depth extends into the room.

RUNS INSIDE BLENDER — the MCP execute_code namespace only has `bpy`, so every block imports its own deps.
"""
import bpy
import math
from mathutils import Vector

MATERIALS = {}


def _clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    MATERIALS.clear()  # factory reset removes materials — drop stale cache
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'
    scene.render.engine = 'BLENDER_EEVEE'


def _mat(name, base=(0.9, 0.9, 0.9), metal=0.0, rough=0.5, transmission=0.0, alpha=1.0):
    key = f"{name}|{base}|{metal}|{rough}|{transmission}|{alpha}"
    if key in MATERIALS:
        return MATERIALS[key]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*base, 1.0)
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Roughness'].default_value = rough
    if transmission > 0:
        bsdf.inputs['Transmission Weight'].default_value = transmission
        bsdf.inputs['Alpha'].default_value = alpha
        mat.blend_method = 'BLEND' if alpha < 1 else 'OPAQUE'
    MATERIALS[key] = mat
    return mat


def chrome():
    return _mat('chrome', (0.83, 0.85, 0.88), metal=1.0, rough=0.08)


def brass():
    return _mat('brushed_brass', (0.78, 0.66, 0.35), metal=1.0, rough=0.32)


def nickel():
    return _mat('brushed_nickel', (0.78, 0.79, 0.80), metal=1.0, rough=0.25)


def matt_black():
    return _mat('matt_black', (0.10, 0.10, 0.11), metal=0.0, rough=0.75)


def white_ceramic():
    return _mat('white_ceramic', (0.97, 0.97, 0.96), metal=0.0, rough=0.18)


def glass_clear():
    return _mat('glass_clear', (0.92, 0.95, 0.97), metal=0.0, rough=0.04, transmission=0.92)


def acrylic_white():
    return _mat('acrylic_white', (0.96, 0.96, 0.95), metal=0.0, rough=0.25)


def stone_resin():
    return _mat('stone_resin', (0.88, 0.86, 0.83), metal=0.0, rough=0.6)


def anthracite():
    return _mat('anthracite', (0.22, 0.22, 0.24), metal=0.6, rough=0.45)


def white_mdf():
    return _mat('white_mdf', (0.95, 0.95, 0.94), metal=0.0, rough=0.5)


def wood_oak():
    return _mat('wood_oak', (0.62, 0.48, 0.32), metal=0.0, rough=0.55)


def glass_mirror():
    return _mat('glass_mirror', (0.85, 0.9, 0.95), metal=0.0, rough=0.02)


def assign(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def _add(name, mat, **kwargs):
    """Add a primitive mesh, name it, assign material, return object."""
    obj = bpy.context.view_layer.objects.active
    if obj is None:
        raise RuntimeError("No active object after primitive add")
    obj.name = name
    assign(obj, mat)
    return obj


def box(name, mat, size, loc=(0, 0, 0), rot=(0, 0, 0), bevel=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    obj = _add(name, mat)
    obj.scale = size
    bpy.ops.object.transform_apply(scale=True)  # bake size so bevel width is in world units
    if bevel:
        mod = obj.modifiers.new('Bevel', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        mod.limit_method = 'ANGLE'
        mod.angle_limit = math.radians(40)
    return obj


def cyl(name, mat, radius, depth, loc=(0, 0, 0), rot=(0, 0, 0), verts=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot)
    return _add(name, mat)


def sphere(name, mat, radius, loc=(0, 0, 0), scale=(1, 1, 1), seg=48):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=seg, ring_count=seg // 2, location=loc)
    obj = _add(name, mat)
    obj.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    return obj


def torus(name, mat, major, minor, loc=(0, 0, 0), rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, location=loc, rotation=rot)
    return _add(name, mat)


def lathe(name, mat, profile_pts, axis='Y', steps=48, close_bottom=True):
    """Surface of revolution: profile_pts = [(r, h), ...] rotated around `axis`.
    Profile r = distance from axis, h = height along axis.
    Open profile (wall only) unless close_bottom: ends at r=0 at h=0 to cap the base."""
    curve = bpy.data.curves.new(f'{name}_curve', 'CURVE')
    curve.dimensions = '2D'
    spline = curve.splines.new('POLY')
    pts = list(profile_pts)
    if close_bottom and pts[0][0] > 0.001:
        pts = [(0.001, pts[0][1])] + pts
    spline.points.add(len(pts) - 1)
    for i, (r, h) in enumerate(pts):
        if axis == 'Y':
            spline.points[i].co = (r, h, 0, 1)
        elif axis == 'Z':
            spline.points[i].co = (r, 0, h, 1)
        else:
            spline.points[i].co = (0, r, h, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    mod = obj.modifiers.new('Screw', 'SCREW')
    mod.axis = axis
    mod.angle = math.pi * 2
    mod.steps = steps
    mod.use_merge_vertices = True
    mod.merge_threshold = 0.0005
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    assign(obj, mat)
    return obj


def delete_top_faces(obj):
    """Delete upward-facing faces (open-box trick for baths)."""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    import bmesh
    bm = bmesh.from_edit_mesh(obj.data)
    for f in bm.faces:
        if f.normal.z > 0.9:
            f.select = True
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.delete(type='FACE')
    bpy.ops.object.mode_set(mode='OBJECT')
    return obj


def _set_origin_back_bottom_center(obj):
    """Origin to world (0,0,0) = local back-bottom-center.
    back = max y (front faces -Y), bottom = min z."""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    offset = Vector(((min(xs) + max(xs)) / 2, max(ys), min(zs)))
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.transform.translate(value=-offset)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')


def _join_all():
    bpy.ops.object.select_all(action='DESELECT')
    for o in bpy.data.objects:
        if o.type == 'MESH':
            # apply modifiers (bevel etc.) before join — glTF export_apply is unreliable here
            for m in list(o.modifiers):
                bpy.context.view_layer.objects.active = o
                o.select_set(True)
                try:
                    bpy.ops.object.modifier_apply(modifier=m.name)
                except RuntimeError:
                    o.modifiers.remove(m)
                o.select_set(False)
            o.select_set(True)
    if len(bpy.context.selected_objects) > 1:
        bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
        bpy.ops.object.join()


def export_glb(slug):
    out = f"C:/Users/Eamon/Desktop/bathroom-3d/assets/models/{slug}.glb"
    _join_all()
    obj = bpy.context.view_layer.objects.active or bpy.context.selected_objects[0]
    _set_origin_back_bottom_center(obj)
    # keep origin at back-bottom-center world (0,0,0)
    obj.location = (0, 0, 0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    try:
        bpy.ops.export_scene.gltf(
            filepath=out,
            export_format='GLB',
            export_yup=True,
            export_apply=True,
            export_draco_mesh_compression_enable=True,
            export_draco_mesh_compression_level=6,
        )
    except TypeError:
        bpy.ops.export_scene.gltf(
            filepath=out,
            export_format='GLB',
            export_apply=True,
            export_draco_mesh_compression_enable=True,
            export_draco_mesh_compression_level=6,
        )
    n_polys = sum(len(m.data.polygons) for m in bpy.data.objects if m.type == 'MESH' and m.data)
    print(f"EXPORTED {slug} polys={n_polys}")


# =====================================================================
# MODEL BUILDERS  (all dims in metres; origin at back-bottom-center)
# =====================================================================

def build_toilet():
    _clean_scene()
    # close-coupled toilet: 360w x 620d x 780h. Back at y=0, front -Y.
    # pan base: full depth, low profile
    box('pan', white_ceramic(), (0.34, 0.62, 0.12), (0, -0.31, 0.06), bevel=0.015)
    # bowl: hollow wall, sits on pan, center y=-0.46
    profile = [(0.001, 0.0), (0.09, 0.03), (0.14, 0.08), (0.16, 0.14), (0.15, 0.20), (0.12, 0.25), (0.15, 0.28)]
    bowl = lathe('bowl', white_ceramic(), profile, axis='Y', steps=40, close_bottom=True)
    bowl.location = (0, -0.46, 0.12)
    # seat ring + lid
    torus('seat', white_ceramic(), 0.15, 0.02, (0, -0.46, 0.40))
    box('lid', white_ceramic(), (0.30, 0.30, 0.018), (0, -0.46, 0.423))
    # cistern: deep slab at back, front face meets bowl back
    box('cistern', white_ceramic(), (0.36, 0.31, 0.44), (0, -0.155, 0.34), bevel=0.015)
    box('cistern_lid', white_ceramic(), (0.36, 0.31, 0.02), (0, -0.155, 0.57))
    cyl('flush', _mat('flush_btn', (0.9, 0.9, 0.9), metal=0.2, rough=0.3), 0.03, 0.01, (0, -0.155, 0.585))
    export_glb('toilet')


def build_basin():
    _clean_scene()
    # pedestal basin: 560w x 470d x 790h. Pedestal column under the bowl, aligned y.
    cy = -0.10
    # pedestal: tapered column
    col = cyl('pedestal', white_ceramic(), 0.085, 0.55, (0, cy, 0.275))
    col.scale = (1.0, 0.8, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    # base plate
    cyl('base_plate', white_ceramic(), 0.12, 0.02, (0, cy, 0.01))
    # bowl: hollow profile (open top rim), sitting on pedestal
    profile = [(0.001, 0.0), (0.12, 0.03), (0.17, 0.08), (0.22, 0.16), (0.24, 0.24), (0.23, 0.30), (0.18, 0.34), (0.15, 0.36)]
    bowl = lathe('bowl', white_ceramic(), profile, axis='Y', steps=40, close_bottom=True)
    bowl.location = (0, cy, 0.55)
    # rim disc (top)
    cyl('rim', white_ceramic(), 0.24, 0.015, (0, cy, 0.55 + 0.36))
    export_glb('basin')


def build_bath():
    _clean_scene()
    w, h, d = 1.7, 0.56, 0.75
    # outer shell: open box (top face deleted), clean edges
    outer = box('outer', acrylic_white(), (w, d, h), (0, -d / 2, h / 2))
    delete_top_faces(outer)
    # inner floor (visible through the opening)
    box('inner_floor', acrylic_white(), (w - 0.18, d - 0.20, 0.05), (0, -d / 2, 0.10), bevel=0.02)
    # rim frame on top edge
    box('rim_front', acrylic_white(), (w, 0.07, 0.035), (0, -d + 0.035, h - 0.017))
    box('rim_back', acrylic_white(), (w, 0.07, 0.035), (0, -0.035, h - 0.017))
    box('rim_l', acrylic_white(), (0.07, d, 0.035), (-w / 2 + 0.035, -d / 2, h - 0.017))
    box('rim_r', acrylic_white(), (0.07, d, 0.035), (w / 2 - 0.035, -d / 2, h - 0.017))
    export_glb('bath')


def build_shower_tray():
    _clean_scene()
    w, h, d = 0.9, 0.04, 0.76
    box('tray', stone_resin(), (w, d, h), (0, -d / 2, h / 2), bevel=0.015)
    # inner recess (visible top step)
    box('recess', stone_resin(), (w - 0.06, d - 0.06, 0.01), (0, -d / 2, h - 0.005))
    # waste hole
    cyl('waste', _mat('waste', (0.15, 0.15, 0.16), metal=0.5, rough=0.4), 0.04, 0.02, (0, -d / 2, h + 0.005))
    export_glb('shower-tray')


def build_shower_screen():
    _clean_scene()
    w, h, d = 0.8, 1.9, 0.008
    # glass panel (origin at back edge; panel extends into room)
    box('glass', glass_clear(), (w, d, h), (0, -d / 2, h / 2))
    fp = 0.025
    box('top_rail', chrome(), (w + fp * 2, fp, fp), (0, -d / 2 - fp / 2, h + fp / 2))
    box('bottom_rail', chrome(), (w + fp * 2, fp, fp), (0, -d / 2 - fp / 2, fp / 2))
    box('side_rail', chrome(), (fp, fp, h), (-(w / 2 + fp / 2), -d / 2 - fp / 2, h / 2))
    # hinge post at back edge
    cyl('hinge', chrome(), 0.015, h, (-w / 2, 0, h / 2))
    export_glb('shower-screen')


def build_shower_enclosure():
    """Corner shower enclosure: two wall-side glass panels + front door panel,
    chrome corner posts + top rails. Generic footprint 900x900x1900mm —
    build_scaled stretches it to the product's real W x D x H."""
    _clean_scene()
    w, d, h = 0.9, 0.9, 1.9
    gt = 0.008   # glass thickness
    fp = 0.03    # profile size
    glass = glass_clear()
    ch = chrome()
    # wall-side panels (left at x=-w/2, right at x=+w/2), spanning the depth
    box('panel_left', glass, (gt, d, h), (-w / 2 + gt / 2, -d / 2, h / 2))
    box('panel_right', glass, (gt, d, h), (w / 2 - gt / 2, -d / 2, h / 2))
    # front door panel across the opening (leaves a door gap toward the left)
    door_w = w - gt * 2
    box('panel_front', glass, (door_w, gt, h), (0, -d + gt / 2, h / 2))
    # chrome corner posts (full height) at the two front corners
    cyl('post_left', ch, 0.02, h, (-w / 2, -d + fp / 2, h / 2))
    cyl('post_right', ch, 0.02, h, (w / 2, -d + fp / 2, h / 2))
    # wall posts where the side panels meet the wall
    cyl('post_wall_l', ch, 0.018, h, (-w / 2, -fp / 2, h / 2))
    cyl('post_wall_r', ch, 0.018, h, (w / 2, -fp / 2, h / 2))
    # top rails along all three edges
    box('rail_front', ch, (w, fp, fp), (0, -d + fp / 2, h + fp / 2))
    box('rail_left', ch, (fp, d, fp), (-w / 2 + fp / 2, -d / 2, h + fp / 2))
    box('rail_right', ch, (fp, d, fp), (w / 2 - fp / 2, -d / 2, h + fp / 2))
    # door handle on the front panel
    box('handle', ch, (0.015, 0.02, 0.32), (-w / 2 + 0.18, -d - 0.015, h * 0.52))
    export_glb('shower-enclosure')


def build_radiator():
    _clean_scene()
    w, h, d = 1.2, 0.6, 0.07
    box('panel', anthracite(), (w, d, h), (0, -d / 2, h / 2), bevel=0.01)
    fins = max(4, int(w / 0.06))
    for i in range(fins):
        x = -w / 2 + (i + 0.5) * (w / fins)
        box(f'fin_{i}', anthracite(), (0.012, d + 0.03, h - 0.10), (x, -d / 2, h / 2))
    cyl('conn1', chrome(), 0.014, 0.05, (-w / 2 + 0.06, -d / 2 - 0.01, 0.05), rot=(math.pi / 2, 0, 0))
    cyl('conn2', chrome(), 0.014, 0.05, (w / 2 - 0.06, -d / 2 - 0.01, 0.05), rot=(math.pi / 2, 0, 0))
    export_glb('radiator')


def build_towel_rail():
    _clean_scene()
    w, h, d = 0.5, 1.2, 0.1
    bar_d, up_d = 0.022, 0.032
    for x in (-w / 2 + up_d / 2, w / 2 - up_d / 2):
        cyl('upright', chrome(), up_d / 2, h, (x, -0.005, h / 2))
    n_bars = max(4, int(h / 0.15))
    spacing = h / (n_bars + 1)
    for i in range(1, n_bars + 1):
        z = spacing * i
        cyl('bar', chrome(), bar_d / 2, w - up_d, (0, -0.015, z), rot=(math.pi / 2, 0, 0))
    # wall fixings
    for x in (-w / 2 + up_d / 2, w / 2 - up_d / 2):
        cyl('fix', chrome(), 0.018, 0.03, (x, 0.012, h * 0.85))
    export_glb('towel-rail')


def build_mirror():
    _clean_scene()
    w, h, d = 0.6, 0.7, 0.025
    box('mirror', glass_mirror(), (w, d, h), (0, -d / 2, h / 2))
    box('frame', chrome(), (w + 0.024, d + 0.006, h + 0.024), (0, -d / 2 - 0.003, h / 2))
    export_glb('mirror')


def build_cabinet():
    _clean_scene()
    w, h, d = 0.6, 0.75, 0.13
    box('cab_body', white_mdf(), (w, d, h), (0, -d / 2, h / 2))
    box('door', white_mdf(), (w - 0.03, 0.016, h - 0.03), (0, -d + 0.008, h / 2))
    box('mirror_front', glass_mirror(), (w - 0.06, 0.002, h - 0.10), (0, -d + 0.017, h / 2))
    cyl('handle', chrome(), 0.008, 0.18, (0, -d + 0.012, h / 2 - 0.10), rot=(math.pi / 2, 0, 0))
    export_glb('cabinet')


def build_vanity_unit():
    _clean_scene()
    w, h, d = 0.6, 0.85, 0.47
    box('vanity_body', wood_oak(), (w, d, h), (0, -d / 2, h / 2))
    # drawer fronts with dark gap lines
    for i, zc in enumerate((0.30, 0.56)):
        box(f'drawer_gap_{i}', _mat('gap', (0.12, 0.10, 0.08), metal=0, rough=0.8), (w - 0.04, 0.006, 0.24), (0, -d + 0.001, zc))
        box(f'drawer_{i}', wood_oak(), (w - 0.06, 0.018, 0.22), (0, -d + 0.006, zc))
        cyl(f'knob_{i}', chrome(), 0.012, 0.05, (0, -d + 0.016, zc), rot=(math.pi / 2, 0, 0))
    # worktop
    box('worktop', _mat('worktop', (0.92, 0.90, 0.88), metal=0, rough=0.35), (w + 0.02, d, 0.03), (0, -d / 2, h + 0.015))
    # basin on top: hollow bowl
    profile = [(0.001, 0.0), (0.10, 0.03), (0.16, 0.08), (0.20, 0.14), (0.21, 0.20), (0.19, 0.25), (0.13, 0.28), (0.11, 0.29)]
    bowl = lathe('basin_top', white_ceramic(), profile, axis='Y', steps=36, close_bottom=True)
    bowl.location = (0, -0.14, h + 0.03)
    export_glb('vanity-unit')


def build_tap():
    _clean_scene()
    base_r, body_h = 0.028, 0.11
    cyl('base', chrome(), 0.038, 0.012, (0, 0, 0.006))
    cyl('body', chrome(), base_r, body_h, (0, -0.02, body_h / 2 + 0.012))
    # spout: horizontal run then drop
    cyl('spout_h', chrome(), 0.015, 0.16, (-0.075, -0.09, 0.10), rot=(0, 0, 0))
    cyl('spout_drop', chrome(), 0.015, 0.10, (-0.155, -0.09, 0.05), rot=(math.pi / 2, 0, 0))
    # aerator tip
    cyl('tip', chrome(), 0.017, 0.008, (-0.155, -0.09, 0.001), rot=(math.pi / 2, 0, 0))
    # lever
    cyl('lever', chrome(), 0.009, 0.06, (0.03, -0.05, body_h + 0.03), rot=(0, 0, math.radians(-25)))
    export_glb('tap')


def build_shower_head():
    _clean_scene()
    # wall-mounted fixed head
    cyl('arm', chrome(), 0.014, 0.22, (0, -0.08, 0.15), rot=(math.radians(90), 0, 0))
    cyl('head', chrome(), 0.09, 0.05, (0, -0.22, 0.19))
    cyl('face', _mat('shower_face', (0.9, 0.9, 0.9), metal=0, rough=0.35), 0.07, 0.006, (0, -0.245, 0.19))
    # wall flange
    cyl('flange', chrome(), 0.025, 0.012, (0, 0.006, 0.15))
    export_glb('shower-head')


def build_shower_set():
    _clean_scene()
    # wall-mounted bar mixer set
    box('valve', chrome(), (0.16, 0.085, 0.20), (0, -0.06, 0.50))
    cyl('knob1', chrome(), 0.034, 0.03, (-0.055, -0.105, 0.50), rot=(math.pi / 2, 0, 0))
    cyl('knob2', chrome(), 0.034, 0.03, (0.055, -0.105, 0.50), rot=(math.pi / 2, 0, 0))
    # slide rail
    cyl('rail', chrome(), 0.011, 0.60, (0.13, -0.015, 0.68))
    cyl('rail_fix1', chrome(), 0.018, 0.03, (0.13, 0.008, 0.45))
    cyl('rail_fix2', chrome(), 0.018, 0.03, (0.13, 0.008, 0.88))
    # handset + holder
    cyl('holder', chrome(), 0.022, 0.06, (0.13, -0.045, 0.82), rot=(math.pi / 2, 0, 0))
    cyl('handset', _mat('handset', (0.85, 0.87, 0.9), metal=0.9, rough=0.2), 0.028, 0.17, (0.10, -0.13, 0.72), rot=(0, math.radians(25), 0))
    # flexible hose loop (approx: torus arc)
    torus('hose', _mat('hose', (0.75, 0.78, 0.82), metal=0.8, rough=0.3), 0.06, 0.009, (0.06, -0.14, 0.55), rot=(math.pi / 2, 0, 0))
    # head on arm
    cyl('arm2', chrome(), 0.013, 0.28, (0, -0.07, 1.15), rot=(math.radians(80), 0, 0))
    cyl('head', chrome(), 0.08, 0.045, (0.02, -0.30, 1.20))
    export_glb('shower-set')


def build_shelf():
    _clean_scene()
    w, h, d = 0.6, 0.015, 0.12
    box('glass_shelf', glass_clear(), (w, d, h), (0, -d / 2, 0.16))
    for x in (-w / 2 + 0.07, w / 2 - 0.07):
        box(f'bracket_{x}', chrome(), (0.03, 0.03, 0.16), (x, -d / 2 - 0.01, 0.08))
    export_glb('shelf')


def build_towel_ring():
    _clean_scene()
    torus('ring', chrome(), 0.07, 0.012, (0, -0.015, 0.10), rot=(math.pi / 2, 0, 0))
    cyl('backplate', chrome(), 0.022, 0.03, (0, 0, 0.10))
    export_glb('towel-ring')


def build_robe_hook():
    _clean_scene()
    cyl('plate', chrome(), 0.024, 0.02, (0, 0, 0.13))
    cyl('hook1', chrome(), 0.008, 0.055, (-0.022, -0.035, 0.10), rot=(0, math.radians(45), 0))
    cyl('hook2', chrome(), 0.008, 0.055, (0.022, -0.035, 0.10), rot=(0, math.radians(45), 0))
    export_glb('robe-hook')


def build_soap_dish():
    _clean_scene()
    box('dish', chrome(), (0.12, 0.09, 0.03), (0, -0.045, 0.035))
    box('backplate', chrome(), (0.06, 0.02, 0.13), (0, 0, 0.10))
    export_glb('soap-dish')


# =====================================================================
# DIMENSION-DRIVEN SCALING (doc 03 §2.2 — models match real product dims)
# =====================================================================

# Finish slug (from products.finishes / scraper normalize) -> material fn.
FINISH_MATERIALS = {
    'chrome': chrome,
    'brushed_brass': brass,
    'satin_brass': brass,
    'brushed_nickel': nickel,
    'polished_nickel': nickel,
    'matt_black': matt_black,
    'black': matt_black,
    'anthracite': anthracite,
    'oak': wood_oak,
    'white': white_mdf,
}

# Material names that swap with the product finish (metallic/furniture parts).
# Ceramic/glass/acrylic keep their own material regardless of finish.
_FINISHABLE = {'chrome', 'brushed_brass', 'brushed_nickel', 'matt_black', 'anthracite', 'oak'}


def build_scaled(slug: str, w_mm: float, h_mm: float, d_mm: float,
                 finish: str | None = None, out_name: str | None = None) -> str:
    """Build the generic model for `slug`, scale it to the product's real
    dimensions (mm), apply the requested finish to finishable parts, and
    export GLB. Returns the absolute output path.

    Scaling is computed from the ACTUAL built bounding box (not hardcoded
    prefer-dimensions), so it tracks the real geometry. Axes missing in the
    product data (None) are left at the generic size.

    out_name: output file stem (defaults to slug). Callers pass a unique name
    per product (e.g. 'model_<id>') so scraped models don't overwrite each other.
    """
    _clean_scene()
    if slug not in BUILDERS:
        raise ValueError(f"no builder for slug '{slug}'")

    BUILDERS[slug]()  # builds the generic shape

    # measure the ACTUAL built dimensions (world axis order: x = w, y = d, z = h)
    bounds = [None, None]
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        m = o.matrix_world
        bb = [m @ Vector(c) for c in o.bound_box]
        bounds[0] = (min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))
        bounds[1] = (max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb))
    if bounds[0] is None:
        raise RuntimeError(f"no mesh built for {slug}")
    a_min, a_max = bounds
    actual = (a_max[0] - a_min[0], a_max[1] - a_min[1], a_max[2] - a_min[2])  # w,d,h metres

    # target in metres (None -> keep actual)
    t = {
        'w': (w_mm or actual[0] * 1000) / 1000.0,   # width  -> x
        'd': (d_mm or actual[1] * 1000) / 1000.0,   # depth  -> y
        'h': (h_mm or actual[2] * 1000) / 1000.0,   # height -> z
    }
    # Blender axes: x=width, y=depth, z=height (origin back-bottom-center)
    scale = (t['w'] / actual[0], t['d'] / actual[1], t['h'] / actual[2])  # x,y,z order

    # apply non-uniform scale to match real dims (origin already at back-bottom-center)
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.scale = (o.scale[0] * scale[0], o.scale[1] * scale[1], o.scale[2] * scale[2])
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.transform_apply(scale=True)

    # finish override on finishable parts
    if finish and finish in FINISH_MATERIALS:
        mat = FINISH_MATERIALS[finish]()
        for o in bpy.data.objects:
            if o.type != 'MESH' or not o.data.materials:
                continue
            mname = o.data.materials[0].name
            if mname in _FINISHABLE:
                assign(o, mat)

    out = out_name or slug
    export_glb(out)
    return f"C:/Users/Eamon/Desktop/bathroom-3d/assets/models/{out}.glb"


BUILDERS = {
    'toilet': build_toilet,
    'basin': build_basin,
    'bath': build_bath,
    'shower-tray': build_shower_tray,
    'shower-screen': build_shower_screen,
    'shower-enclosure': build_shower_enclosure,
    'radiator': build_radiator,
    'towel-rail': build_towel_rail,
    'mirror': build_mirror,
    'cabinet': build_cabinet,
    'vanity-unit': build_vanity_unit,
    'tap': build_tap,
    'shower-head': build_shower_head,
    'shower-set': build_shower_set,
    'shelf': build_shelf,
    'towel-ring': build_towel_ring,
    'robe-hook': build_robe_hook,
    'soap-dish': build_soap_dish,
}

# Executed by blender_headless.py (module import) or blender_driver.py (exec with BUILD injected)
def run_build(slug: str):
    if slug in BUILDERS:
        BUILDERS[slug]()
        print(f"BUILD_OK {slug}")
    else:
        print(f"UNKNOWN_BUILD {slug}")


if "BUILD" in globals():
    run_build(BUILD)

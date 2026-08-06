"""Dimension-driven archetype builders for the Bathroom-3D model catalogue.

Executed INSIDE Blender (5.2) via the ahujasid MCP addon's execute_code:
    exec(open(r'C:/Users/Eamon/Desktop/bathroom-3d/packages/model-gen/mcp_builders.py').read())
    build_one('bath-se-rect-rect')

Conventions (same as blender_lib.py, but dims are BUILD INPUTS - never post-stretch):
- Blender metres; origin at BACK-BOTTOM-CENTER; front faces -Y (back against wall).
- After yup GLB export: front faces +Z in Three.js; editor loads at scale 1000 (mm).
- build_one(slug): clean scene -> build -> export GLB -> render EEVEE thumbnail +
  QA check render -> print 'DONE <slug>'.
- NEVER use bpy.ops.wm.read_factory_settings over the MCP socket (kills the server).
"""
import bpy
import math
import os
from mathutils import Vector

ROOT = r"C:/Users/Eamon/Desktop/bathroom-3d"
MODELS = os.path.join(ROOT, "assets", "models")
THUMBS = os.path.join(ROOT, "assets", "thumbnails")
QA = os.path.join(ROOT, "assets", "qa_probe")
os.makedirs(MODELS, exist_ok=True)
os.makedirs(THUMBS, exist_ok=True)
os.makedirs(QA, exist_ok=True)

MATERIALS = {}


def _clean():
    """Manual scene clean (factory reset kills the MCP socket server)."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for c in list(bpy.data.curves):
        bpy.data.curves.remove(c)
    MATERIALS.clear()
    s = bpy.context.scene
    s.unit_settings.system = 'METRIC'
    s.unit_settings.scale_length = 1.0
    s.unit_settings.length_unit = 'METERS'
    s.render.engine = 'BLENDER_EEVEE'


def mat(name, base, metal=0.0, rough=0.5, emission=None, alpha=1.0):
    key = (name, base, metal, rough, emission, alpha)
    if key in MATERIALS:
        return MATERIALS[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*base, alpha)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if emission:
        b.inputs['Emission Color'].default_value = (*emission, 1.0)
        b.inputs['Emission Strength'].default_value = 4.0
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        m.blend_method = 'BLEND'
    MATERIALS[key] = m
    return m


# --- palette ---
def m_white():      return mat('acrylic_white', (0.97, 0.97, 0.96), 0, 0.22)
def m_ceramic():    return mat('white_ceramic', (0.98, 0.98, 0.97), 0, 0.15)
def m_stone():      return mat('stone_resin', (0.90, 0.89, 0.87), 0, 0.55)
def m_glass():      return mat('glass_clear', (0.92, 0.95, 0.97), 0, 0.05, None, 0.18)
def m_glass_frost():return mat('glass_frosted', (0.90, 0.92, 0.94), 0, 0.35, None, 0.45)
def m_chrome():     return mat('chrome', (0.83, 0.85, 0.88), 1.0, 0.08)
def m_gold():       return mat('gold', (0.83, 0.65, 0.28), 1.0, 0.22)
def m_bronze():     return mat('bronze', (0.62, 0.45, 0.30), 1.0, 0.32)
def m_silver():     return mat('silver', (0.80, 0.81, 0.82), 1.0, 0.20)
def m_black():      return mat('matt_black', (0.10, 0.10, 0.11), 0, 0.7)
def m_anthracite(): return mat('anthracite', (0.22, 0.22, 0.24), 0.6, 0.45)
def m_oak():        return mat('wood_oak', (0.62, 0.48, 0.32), 0, 0.55)
def m_mdf():        return mat('white_mdf', (0.95, 0.95, 0.94), 0, 0.5)
def m_mirror():     return mat('mirror_face', (0.86, 0.90, 0.95), 1.0, 0.03)
def m_led():        return mat('led_strip', (1, 1, 1), 0, 0.4, (1.0, 0.98, 0.92))
def m_waste():      return mat('waste_dark', (0.15, 0.15, 0.16), 0.5, 0.4)
def m_gap():        return mat('gap_dark', (0.10, 0.09, 0.08), 0, 0.8)


def _add(obj, name, m):
    obj.name = name
    if obj.data.materials:
        obj.data.materials[0] = m
    else:
        obj.data.materials.append(m)
    return obj


def box(name, m, size, loc=(0, 0, 0), rot=(0, 0, 0), bevel=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    o = _add(bpy.context.view_layer.objects.active, name, m)
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        md = o.modifiers.new('B', 'BEVEL')
        md.width = bevel
        md.segments = 2
        md.limit_method = 'ANGLE'
        md.angle_limit = math.radians(30)
    return o


def cyl(name, m, r, depth, loc=(0, 0, 0), rot=(0, 0, 0), verts=28):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                        location=loc, rotation=rot)
    return _add(bpy.context.view_layer.objects.active, name, m)


def sphere(name, m, r, loc=(0, 0, 0), scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=36, ring_count=18, radius=r, location=loc)
    o = _add(bpy.context.view_layer.objects.active, name, m)
    o.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    return o


def ellipsoid(name, m, rx, ry, rz, loc=(0, 0, 0)):
    return sphere(name, m, 0.5, loc, (rx * 2, ry * 2, rz * 2))


def lathe(name, m, prof, axis='Z', steps=40, close_bottom=True):
    """Surface of revolution. prof = [(radius, height_along_axis), ...]."""
    curve = bpy.data.curves.new(name + '_c', 'CURVE')
    curve.dimensions = '2D'
    pts = list(prof)
    if close_bottom and pts[0][0] > 0.001:
        pts = [(0.001, pts[0][1])] + pts
    sp = curve.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for i, (r, h) in enumerate(pts):
        if axis == 'Z':
            sp.points[i].co = (r, 0, h, 1)
        elif axis == 'Y':
            sp.points[i].co = (r, h, 0, 1)
        else:
            sp.points[i].co = (0, r, h, 1)
    o = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(o)
    md = o.modifiers.new('Screw', 'SCREW')
    md.axis = axis
    md.angle = math.pi * 2
    md.steps = steps
    md.use_merge_vertices = True
    md.merge_threshold = 0.0005
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.convert(target='MESH')
    _add(o, name, m)
    return o


def quarter_disc(name, m, r, h, center=(0, 0), n=18):
    """Quarter-circle sector (plan), extruded to height h. Arc sweeps from the
    +x direction to the -y direction around `center`. Used for quadrant tray
    corners and rounded-corner baths. Built via bmesh fan + extrude."""
    import bmesh
    bm = bmesh.new()
    c = bm.verts.new((0, 0, 0))
    arc = []
    for i in range(n + 1):
        th = -math.pi / 2 * i / n
        arc.append(bm.verts.new((r * math.cos(th), r * math.sin(th), 0)))
    bm.verts.ensure_lookup_table()
    for i in range(n):
        bm.faces.new([c, arc[i + 1], arc[i]])
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    for v in ret['geom']:
        if isinstance(v, bmesh.types.BMVert):
            v.co.z += h
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.location = (center[0], center[1], 0)
    return _add(o, name, m)


def delete_top_faces(obj):
    """Delete upward-facing faces. NOTE: operator-based selection delete is
    unreliable via MCP (silently deletes nothing) — use bmesh.ops.delete."""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    import bmesh
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    victims = [f for f in bm.faces if f.normal.z > 0.9]
    if victims:
        bmesh.ops.delete(bm, geom=victims, context='FACES')
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    return obj


def open_ellipse_shell(name, m, w, d, h, loc_y):
    """Elliptical open-top shell (freestanding bath body): scaled cylinder, top deleted."""
    o = cyl(name, m, 0.5, h, (0, loc_y, h / 2))
    o.scale = (w, d, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    return delete_top_faces(o)


def set_origin_back_bottom_center():
    """Join all meshes, move origin to back-bottom-center at world (0,0,0)."""
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    if not meshes:
        raise RuntimeError("no meshes")
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        for md in list(o.modifiers):
            bpy.context.view_layer.objects.active = o
            o.select_set(True)
            try:
                bpy.ops.object.modifier_apply(modifier=md.name)
            except RuntimeError:
                o.modifiers.remove(md)
            o.select_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    off = Vector(((min(xs) + max(xs)) / 2, max(ys), min(zs)))
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.transform.translate(value=-off)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    obj.location = (0, 0, 0)
    bpy.ops.object.transform_apply(location=True)
    return obj


def export_glb(slug):
    path = os.path.join(MODELS, f"{slug}.glb").replace("\\", "/")
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_yup=True,
                              export_apply=True,
                              export_draco_mesh_compression_enable=True,
                              export_draco_mesh_compression_level=6)
    return path


def _frame_camera(direction, dist_mult=2.3):
    obj = bpy.context.view_layer.objects.active
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    center = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    diag = Vector((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))).length
    dirv = Vector(direction).normalized()
    cam_pos = center + dirv * diag * dist_mult
    cam_d = bpy.data.cameras.new('Cam')
    cam_d.lens = 50
    cam = bpy.data.objects.new('Cam', cam_d)
    cam.location = cam_pos
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = Vector((0, 0, -1)).rotation_difference((center - cam_pos).normalized())
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return center


def _lights():
    world = bpy.data.worlds.new('W')
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    bg.inputs[0].default_value = (0.85, 0.85, 0.85, 1)
    bg.inputs[1].default_value = 1.0
    bpy.context.scene.world = world
    for nm, en, rot in (("Key", 4.5, (math.radians(55), 0, math.radians(-50))),
                        ("Fill", 2.0, (math.radians(30), 0, math.radians(120))),
                        ("Rim", 1.2, (math.radians(75), 0, math.radians(210)))):
        L = bpy.data.objects.new(nm, bpy.data.lights.new(nm, 'SUN'))
        L.rotation_euler = rot
        L.data.energy = en
        bpy.context.scene.collection.objects.link(L)


def render_thumb(slug, size=256):
    s = bpy.context.scene
    s.render.engine = 'BLENDER_EEVEE'
    s.render.resolution_x = size
    s.render.resolution_y = size
    s.render.image_settings.file_format = 'PNG'
    _lights()
    _frame_camera((1, -0.9, 0.75))
    s.render.film_transparent = True
    s.render.filepath = os.path.join(THUMBS, f"{slug}.png").replace("\\", "/")
    bpy.ops.render.render(write_still=True)


def render_qa(slug, size=768):
    """Dark-background QA render for vision comparison (transparent glass reads
    invisible on grey; dark bg makes white + glass legible)."""
    s = bpy.context.scene
    s.render.film_transparent = False
    s.render.resolution_x = size
    s.render.resolution_y = size
    bg = s.world.node_tree.nodes.get('Background')
    bg.inputs[0].default_value = (0.30, 0.30, 0.32, 1)
    _frame_camera((1, -0.9, 0.75), 2.5)
    s.render.filepath = os.path.join(QA, f"{slug}_check.png").replace("\\", "/")
    bpy.ops.render.render(write_still=True)


# =====================================================================
# BATHS (17) — all panel/built-in baths include side panels; dims in m
# =====================================================================

def _bath_shell_with_panels(name_prefix, w, h, d, panels=('front', 'left', 'right')):
    """Rectangular open shell (top deleted) + inner floor + rim + side panels."""
    t = 0.012  # shell visual thickness (rim)
    outer = box(f'{name_prefix}_outer', m_white(), (w, d, h), (0, -d / 2, h / 2))
    delete_top_faces(outer)
    box(f'{name_prefix}_floor', m_white(), (w - 0.16, d - 0.16, 0.04), (0, -d / 2, 0.10), bevel=0.015)
    # rim
    rt = 0.055
    box(f'{name_prefix}_rim_f', m_white(), (w, rt, 0.03), (0, -d + rt / 2, h - 0.015))
    box(f'{name_prefix}_rim_b', m_white(), (w, rt, 0.03), (0, -rt / 2, h - 0.015))
    box(f'{name_prefix}_rim_l', m_white(), (rt, d, 0.03), (-w / 2 + rt / 2, -d / 2, h - 0.015))
    box(f'{name_prefix}_rim_r', m_white(), (rt, d, 0.03), (w / 2 - rt / 2, -d / 2, h - 0.015))
    # built-in side panels (texturable in canvas later)
    ph = h - 0.03
    if 'front' in panels:
        box(f'{name_prefix}_panel_front', m_mdf(), (w - 0.02, 0.018, ph), (0, -d - 0.009, ph / 2))
    if 'left' in panels:
        box(f'{name_prefix}_panel_left', m_mdf(), (0.018, d, ph), (-w / 2 - 0.009, -d / 2, ph / 2))
    if 'right' in panels:
        box(f'{name_prefix}_panel_right', m_mdf(), (0.018, d, ph), (w / 2 + 0.009, -d / 2, ph / 2))


def _ellipse_opening(name_prefix, w, d, h, inset=0.10):
    """Elliptical (round-ended) opening: open elliptical shell nested inside rim."""
    iw, idp = w - inset * 2, d - inset * 2
    inner = open_ellipse_shell(f'{name_prefix}_open', m_white(), iw, idp, h - 0.02, 0)
    # tub spans y=0 (back) to y=-d (front); center the opening at y=-d/2
    inner.location = (0, -d / 2, 0.03)
    # inner floor visible at the bottom of the bowl
    f = cyl(f'{name_prefix}_ifloor', m_white(), 0.5, 0.03, (0, -d / 2, 0.12))
    f.scale = (iw - 0.18, idp - 0.18, 1)
    bpy.ops.object.transform_apply(scale=True)


def build_bath_se_rect_rect(w=1.70, h=0.56, d=0.75):
    _bath_shell_with_panels('bath', w, h, d)  # rectangular opening = rim only, no ellipse


def build_bath_se_rect_round(w=1.70, h=0.56, d=0.75):
    _bath_shell_with_panels('bath', w, h, d)
    _ellipse_opening('bath', w, d, h)


def build_bath_se_asym(w=1.70, h=0.56, d=0.75):
    """Square tap-end + round far end opening."""
    _bath_shell_with_panels('bath', w, h, d)
    # opening: rounded rect = full inner floor + round-end ellipse bulge at -Y end
    iw, idp = w - 0.20, d - 0.20
    f = cyl('bath_ifloor', m_white(), 0.5, 0.03, (0, -d / 2, 0.12))
    f.scale = (iw, idp, 1)
    bpy.ops.object.transform_apply(scale=True)
    # round the far (front) end of the opening with a nested half-shell
    half = open_ellipse_shell('bath_round_end', m_white(), idp, idp, h - 0.03, 0)
    half.location = (0, -d + idp / 2, 0.04)


def build_bath_de_rect_rect(w=1.80, h=0.58, d=0.80):
    _bath_shell_with_panels('bath', w, h, d)


def build_bath_de_rect_round(w=1.80, h=0.58, d=0.80):
    _bath_shell_with_panels('bath', w, h, d)
    _ellipse_opening('bath', w, d, h)


def build_bath_btw_dshape(w=1.70, h=0.56, d=0.75):
    """Back-to-wall D-shape: flat back, curved front, built-in front panel."""
    r = d
    body = box('bath_body', m_white(), (w, d - r / 2, h), (0, -(d - r / 2) / 2, h / 2))
    delete_top_faces(body)
    # D curve: half-ellipse across the front
    bulge = cyl('bath_bulge', m_white(), 0.5, h, (0, -(d - r / 2), h / 2))
    bulge.scale = (w, r, 1)
    bpy.ops.object.transform_apply(scale=True)
    delete_top_faces(bulge)
    f = cyl('bath_ifloor', m_white(), 0.5, 0.03, (0, -d / 2, 0.12))
    f.scale = (w - 0.22, d - 0.18, 1)
    bpy.ops.object.transform_apply(scale=True)
    rt = 0.05
    box('bath_rim_b', m_white(), (w, rt, 0.03), (0, -rt / 2, h - 0.015))
    box('bath_panel_front', m_mdf(), (w - 0.02, 0.018, h - 0.03), (0, -d - 0.009, (h - 0.03) / 2))
    box('bath_panel_left', m_mdf(), (0.018, d, h - 0.03), (-w / 2 - 0.009, -d / 2, (h - 0.03) / 2))
    box('bath_panel_right', m_mdf(), (0.018, d, h - 0.03), (w / 2 + 0.009, -d / 2, (h - 0.03) / 2))


def _btw_offset(w, h, d, right_hand):
    """Offset back-to-wall bath: rectangular with a bulged wider shoulder on one end."""
    _bath_shell_with_panels('bath', w, h, d)
    sx = w / 4 if right_hand else -w / 4
    bulge = open_ellipse_shell('bath_shoulder', m_white(), w / 2, d + 0.08, h, 0)
    bulge.location = (sx, -d / 2, 0.0)


def build_bath_btw_left(w=1.70, h=0.56, d=0.75):
    _btw_offset(w, h, d, right_hand=False)


def build_bath_btw_right(w=1.70, h=0.56, d=0.75):
    _btw_offset(w, h, d, right_hand=True)


def build_bath_btw_caversham(w=1.70, h=0.56, d=0.75):
    """Ridged front panel (Caversham)."""
    _bath_shell_with_panels('bath', w, h, d, panels=('left', 'right'))
    n = max(6, int(w / 0.16))
    ph = h - 0.03
    for i in range(n):
        x = -w / 2 + (i + 0.5) * (w / n)
        box(f'bath_ridge_{i}', m_mdf(), (w / n * 0.55, 0.028, ph), (x, -d - 0.014, ph / 2))
    box('bath_panel_base', m_mdf(), (w - 0.02, 0.012, ph), (0, -d - 0.006, ph / 2))


def _corner_bath(w, h, d, curved):
    """Corner bath: pentagon plan (square corner cut) or curved front (Whitchurch)."""
    r = min(w, d) * 0.55
    body = box('bath_body', m_white(), (w, d - r, h), (0, -(d - r) / 2, h / 2))
    delete_top_faces(body)
    side = box('bath_side', m_white(), (w - r, r, h), (-(r / 2), -(d - r) - r / 2, h / 2))
    delete_top_faces(side)
    if curved:
        quarter_disc('bath_corner', m_white(), r, h, center=(w / 2 - r, -(d - r)))
        delete_top_faces(bpy.data.objects['bath_corner'])
    else:
        # angled flat front: 3-vertex prism across the diagonal
        prism = cyl('bath_corner', m_white(), r, h, (w / 2 - r, -(d - r) - r, h / 2),
                    rot=(0, 0, math.radians(135)), verts=3)
        delete_top_faces(prism)
    f = cyl('bath_ifloor', m_white(), 0.5, 0.03, (0, -d / 2, 0.12))
    f.scale = (w - 0.2, d - 0.2, 1)
    bpy.ops.object.transform_apply(scale=True)
    box('bath_panel_front', m_mdf(), (w - 0.02, 0.018, h - 0.03), (0, -d - 0.009, (h - 0.03) / 2))
    box('bath_panel_left', m_mdf(), (0.018, d, h - 0.03), (-w / 2 - 0.009, -d / 2, (h - 0.03) / 2))


def build_bath_corner_generic(w=1.40, h=0.56, d=1.40):
    _corner_bath(w, h, d, curved=False)


def build_bath_corner_whitchurch(w=1.45, h=0.56, d=1.45):
    _corner_bath(w, h, d, curved=True)


def _freestanding(w, h, d, style):
    """styles: plinth | feet | slipper | round | boat"""
    # lift the shell so plinth/feet are visible beneath it (else hidden inside)
    lift = 0.07 if style == 'plinth' else (0.09 if style == 'feet' else 0.0)
    body = open_ellipse_shell('bath_body', m_white(), w, d, h, -d / 2)
    body.location.z = lift
    f = cyl('bath_ifloor', m_white(), 0.5, 0.03, (0, -d / 2, 0.13 + lift))
    f.scale = (w - 0.24, d - 0.24, 1)
    bpy.ops.object.transform_apply(scale=True)
    if style == 'plinth':
        p = cyl('bath_plinth', m_white(), 0.5, 0.09, (0, -d / 2, 0.045))
        p.scale = (w - 0.28, d - 0.24, 1)
        bpy.ops.object.transform_apply(scale=True)
    elif style == 'feet':
        for sx in (-1, 1):
            for sy in (-1, 1):
                foot = cyl('bath_foot', m_chrome(), 0.035, 0.11,
                           (sx * (w / 2 - 0.18), -d / 2 + sy * (d / 2 - 0.15), 0.055))
                foot.scale = (1, 1, 1)
    elif style == 'slipper':
        body2 = open_ellipse_shell('bath_raised', m_white(), w * 0.42, d, h + 0.12, 0)
        body2.location = (w * 0.22, -d * 0.28, 0)
    elif style == 'round':
        pass  # body is already round; no plinth (sits flush)
    elif style == 'boat':
        for sx in (-1, 1):
            end = ellipsoid('bath_end', m_white(), w * 0.08, d / 2, h * 0.62,
                            (sx * (w / 2 - w * 0.04), -d / 2, h * 0.55))


def build_bath_fs_plinth(w=1.70, h=0.58, d=0.75):
    _freestanding(w, h, d, 'plinth')


def build_bath_fs_feet(w=1.70, h=0.58, d=0.75):
    _freestanding(w, h, d, 'feet')


def build_bath_fs_slipper(w=1.70, h=0.62, d=0.75):
    _freestanding(w, h, d, 'slipper')


def build_bath_fs_round(w=1.50, h=0.58, d=1.50):
    _freestanding(w, h, d, 'round')


def build_bath_fs_boat(w=1.80, h=0.60, d=0.80):
    _freestanding(w, h, d, 'boat')


def _shower_bath(w, h, d, p_shape):
    """P-shape: shower bulge on the tap end (+X); L-shape: bulge mid-side (-Y front)."""
    _bath_shell_with_panels('bath', w, h, d, panels=('front', 'left', 'right'))
    bw, bd = 0.85, d + 0.15
    if p_shape:
        bx = w / 2 - bw / 2
        b = box('bath_pbulge', m_white(), (bw, bd, h), (bx, -bd / 2, h / 2))
        delete_top_faces(b)
        p = box('bath_ppanel', m_mdf(), (bw, 0.018, h - 0.03), (bx, -bd - 0.009, (h - 0.03) / 2))
    else:
        bx = -w / 2 + bw / 2
        b = box('bath_lbulge', m_white(), (bw, bd, h), (bx, -bd / 2, h / 2))
        delete_top_faces(b)
        box('bath_lpanel', m_mdf(), (bw, 0.018, h - 0.03), (bx, -bd - 0.009, (h - 0.03) / 2))


def build_bath_p_shape(w=1.70, h=0.56, d=0.75):
    _shower_bath(w, h, d, p_shape=True)


def build_bath_l_shape(w=1.70, h=0.56, d=0.75):
    _shower_bath(w, h, d, p_shape=False)


# =====================================================================
# SCREENS (6)
# =====================================================================

def _glass_panel(name, w, h, t=0.008, frosted=False, loc=(0, 0, 0), rot=(0, 0, 0)):
    return box(name, m_glass_frost() if frosted else m_glass(), (w, t, h), loc, rot)


def build_screen_static_square(w=0.80, h=1.90, d=0.008):
    _glass_panel('glass', w, h, d, loc=(0, -d / 2, h / 2))
    box('top_rail', m_chrome(), (w + 0.03, 0.03, 0.03), (0, -d / 2, h + 0.015))
    box('wall_channel', m_chrome(), (0.03, 0.03, h), (w / 2 + 0.015, -d / 2, h / 2))
    cyl('brace', m_chrome(), 0.011, 0.32, (w / 2 - 0.06, -d / 2 - 0.16, h + 0.01), rot=(math.pi / 2, 0, 0))


def build_screen_static_rounded(w=0.80, h=1.90, d=0.008):
    g = _glass_panel('glass', w, h, d, loc=(0, -d / 2, h / 2), )
    # rounded top corner: cut illusion via angled top cap + curved corner strip
    box('top_rail', m_chrome(), (w * 0.72, 0.03, 0.03), (-w * 0.14, -d / 2, h + 0.015))
    arc_r = w * 0.28
    n = 5
    for i in range(n):
        th0 = math.pi / 2 * i / n
        th1 = math.pi / 2 * (i + 1) / n
        cx, cy = w / 2 - arc_r, h - arc_r
        x0, y0 = cx + arc_r * math.cos(th0), cy + arc_r * math.sin(th0)
        x1, y1 = cx + arc_r * math.cos(th1), cy + arc_r * math.sin(th1)
        chord = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        box(f'corner_{i}', m_chrome(), (chord + 0.005, 0.03, 0.03),
            ((x0 + x1) / 2, -d / 2, (y0 + y1) / 2), rot=(0, 0, ang))
    box('wall_channel', m_chrome(), (0.03, 0.03, h), (-w / 2 - 0.015, -d / 2, h / 2))


def build_screen_hinged(w=1.20, h=1.90, d=0.008):
    """Two-panel hinged/folding screen; hinge line at centre."""
    hw = w / 2
    _glass_panel('panel_fixed', hw, h, d, loc=(-hw / 2, -d / 2, h / 2))
    _glass_panel('panel_moving', hw, h, d, loc=(hw / 2, -d / 2 - 0.04, h / 2), rot=(0, 0, 0))
    # hinge barrel
    cyl('hinge_top', m_chrome(), 0.014, 0.08, (0, -d / 2 - 0.02, h - 0.15))
    cyl('hinge_bot', m_chrome(), 0.014, 0.08, (0, -d / 2 - 0.02, 0.15))
    box('wall_channel', m_chrome(), (0.03, 0.03, h), (-w - 0.015 + hw, -d / 2, h / 2))
    box('top_rail', m_chrome(), (hw + 0.03, 0.03, 0.03), (-hw / 2, -d / 2, h + 0.015))


def build_screen_curved(w=1.40, h=1.50, d=0.008):
    """Curved bath screen: faceted arc following a bath's curve."""
    r = w / 2
    n = 7
    cx, cy = 0, 0
    for i in range(n):
        th0 = math.pi * (0.15 + 0.7 * i / n)
        th1 = math.pi * (0.15 + 0.7 * (i + 1) / n)
        x0, y0 = cx + r * math.cos(th0), cy - r * math.sin(th0)
        x1, y1 = cx + r * math.cos(th1), cy - r * math.sin(th1)
        chord = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        box(f'arc_{i}', m_glass(), (chord, d, h), ((x0 + x1) / 2, (y0 + y1) / 2 - r * 0.25, h / 2),
            rot=(0, 0, ang))
    box('top_rail', m_chrome(), (w * 0.8, 0.03, 0.03), (0, -r * 0.25 - r * 0.55, h + 0.015))


def build_screen_sliding_straight(w=1.20, h=1.90, d=0.008):
    _glass_panel('panel_back', w, h, d, loc=(0, -d / 2, h / 2))
    _glass_panel('panel_slide', w * 0.55, h - 0.06, d, loc=(-w * 0.15, -d / 2 - 0.03, h / 2))
    box('top_rail', m_chrome(), (w + 0.04, 0.04, 0.06), (0, -d / 2 - 0.015, h + 0.02))
    box('bottom_rail', m_chrome(), (w + 0.04, 0.04, 0.06), (0, -d / 2 - 0.015, 0.03))
    box('handle', m_chrome(), (0.02, 0.03, 0.25), (-w * 0.15 + w * 0.27, -d / 2 - 0.05, h * 0.5))


def build_screen_sliding_curved(w=1.40, h=1.50, d=0.008):
    r = w / 2
    n = 8
    for i in range(n):
        th0 = math.pi * (0.1 + 0.8 * i / n)
        th1 = math.pi * (0.1 + 0.8 * (i + 1) / n)
        x0, y0 = r * math.cos(th0), -r * math.sin(th0)
        x1, y1 = r * math.cos(th1), -r * math.sin(th1)
        chord = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        # alternate radius for the sliding panel (overlaps)
        rad = r if i % 2 == 0 else r - 0.035
        xx0, yy0 = rad * math.cos(th0), -rad * math.sin(th0)
        xx1, yy1 = rad * math.cos(th1), -rad * math.sin(th1)
        ch = math.hypot(xx1 - xx0, yy1 - yy0)
        box(f'arc_{i}', m_glass(), (ch, d, h - 0.05 if i % 2 else h),
            ((xx0 + xx1) / 2, (yy0 + yy1) / 2 - r * 0.2, (h - 0.05 if i % 2 else h) / 2),
            rot=(0, 0, math.atan2(yy1 - yy0, xx1 - xx0)))
    box('top_rail', m_chrome(), (w * 0.85, 0.035, 0.05), (0, -r * 0.75, h + 0.017))


# =====================================================================
# ENCLOSURES (14) — glass + chrome frames
# =====================================================================

def _enc_frame(w, d, h, fp=0.035, posts=True):
    ch = m_chrome()
    if posts:
        for x, y in ((-w / 2, -0.02), (w / 2, -0.02)):
            cyl(f'post_{x}', ch, 0.02, h, (x, y, h / 2))
    box('rail_front', ch, (w + fp, fp, fp), (0, -d + fp / 2, h + fp / 2))
    box('rail_left', ch, (fp, d, fp), (-w / 2 - fp / 2 + fp, -d / 2, h + fp / 2))
    box('rail_right', ch, (fp, d, fp), (w / 2 + fp / 2 - fp, -d / 2, h + fp / 2))


def _side_panels(w, d, h, t=0.008):
    box('panel_left', m_glass(), (t, d, h), (-w / 2 + t / 2, -d / 2, h / 2))
    box('panel_right', m_glass(), (t, d, h), (w / 2 - t / 2, -d / 2, h / 2))


def _front_sliding(w, d, h, double):
    t = 0.008
    if double:
        _glass_panel('door_l', w * 0.52, h - 0.04, t, loc=(-w * 0.24, -d + t / 2, h / 2))
        _glass_panel('door_r', w * 0.52, h - 0.04, t, loc=(w * 0.24, -d + t / 2 + 0.02, h / 2))
    else:
        _glass_panel('door_fixed', w * 0.45, h - 0.04, t, loc=(-w * 0.27, -d + t / 2, h / 2))
        _glass_panel('door_slide', w * 0.55, h - 0.04, t, loc=(w * 0.2, -d + t / 2 + 0.02, h / 2))
    box('door_handle', m_chrome(), (0.02, 0.03, 0.30), (w * 0.35, -d - 0.02, h * 0.5))


def _front_bifold(w, d, h, double):
    t = 0.008
    n = 4 if double else 2
    pw = w / n
    for i in range(n):
        x = -w / 2 + pw * (i + 0.5)
        ang = math.radians(18 if i % 2 == 0 else -18)
        _glass_panel(f'fold_{i}', pw * 0.98, h - 0.04, t, loc=(x, -d + 0.02, h / 2), rot=(0, 0, ang))
    box('door_handle', m_chrome(), (0.02, 0.03, 0.28), (0, -d - 0.03, h * 0.5))


def _corner_enclosure(w, d, h, door, rounded):
    if rounded:
        r = d
        n = 6
        cx = -w / 2
        ch = m_chrome()
        prev = None
        for i in range(n + 1):
            th = math.pi / 2 * i / n
            px, py = cx + r * math.cos(th), -r * math.sin(th)
            if prev is not None:
                mx, my = (prev[0] + px) / 2, (prev[1] + py) / 2
                chord = math.hypot(px - prev[0], py - prev[1])
                ang = math.atan2(py - prev[1], px - prev[0])
                box(f'arc_panel_{i}', m_glass(), (chord, 0.008, h), (mx, my, h / 2), rot=(0, 0, ang))
                box(f'arc_rail_{i}', ch, (chord + 0.01, 0.03, 0.03), (mx, my, h + 0.015), rot=(0, 0, ang))
            prev = (px, py)
        cyl('post_back', ch, 0.02, h, (cx + r, -0.02, h / 2))
        cyl('post_front', ch, 0.02, h, (cx + 0.02, -r, h / 2))
        box('panel_right', m_glass(), (0.008, d, h), (w / 2 - 0.004, -d / 2, h / 2))
        box('rail_right', ch, (0.03, d, 0.03), (w / 2 - 0.015, -d / 2, h + 0.015))
        if door != 'open':
            mid = math.pi / 4
            hx, hy = cx + r * math.cos(mid), -r * math.sin(mid)
            box('door_handle', ch, (0.015, 0.02, 0.30), (hx + 0.10, hy - 0.02, h * 0.52))
    else:
        _side_panels(w, d, h)
        _enc_frame(w, d, h)
        box('panel_back_left', m_glass(), (w * 0.3, 0.008, h), (-w * 0.35, -d + 0.004, h / 2))
        if door == 'sliding':
            _front_sliding(w, d, h, double=False)
        elif door == 'double-sliding':
            _front_sliding(w, d, h, double=True)
        elif door == 'bifold':
            _front_bifold(w, d, h, double=False)
        elif door == 'double-bifold':
            _front_bifold(w, d, h, double=True)
        elif door == 'panel':
            _glass_panel('panel_front', w, h - 0.02, 0.008, loc=(0, -d + 0.004, h / 2))
        # 'open': no door glass


def build_enc_corner_sq_sliding(w=0.90, d=0.90, h=1.90): _corner_enclosure(w, d, h, 'sliding', False)
def build_enc_corner_sq_dsliding(w=0.90, d=0.90, h=1.90): _corner_enclosure(w, d, h, 'double-sliding', False)
def build_enc_corner_sq_bifold(w=0.90, d=0.90, h=1.90): _corner_enclosure(w, d, h, 'bifold', False)
def build_enc_corner_sq_open(w=0.90, d=0.90, h=1.90): _corner_enclosure(w, d, h, 'open', False)
def build_enc_corner_sq_panel(w=0.90, d=0.90, h=1.90): _corner_enclosure(w, d, h, 'panel', False)
def build_enc_quadrant_sliding(w=0.90, d=0.90, h=1.90): _corner_enclosure(w, d, h, 'sliding', True)
def build_enc_quadrant_bifold(w=0.90, d=0.90, h=1.90): _corner_enclosure(w, d, h, 'bifold', True)
def build_enc_quadrant_open(w=0.90, d=0.90, h=1.90): _corner_enclosure(w, d, h, 'open', True)


def _midwall_enclosure(w, d, h, door):
    """3-sided enclosure against a mid-wall: left/right/back panels + front door."""
    _side_panels(w, d, h)
    box('panel_back', m_glass(), (w, 0.008, h), (0, -0.004, h / 2))
    _enc_frame(w, d, h)
    if door == 'sliding':
        _front_sliding(w, d, h, double=False)
    elif door == 'double-bifold':
        _front_bifold(w, d, h, double=True)
    # 'open': no front glass


def build_enc_midwall_sliding(w=1.20, d=0.90, h=1.90): _midwall_enclosure(w, d, h, 'sliding')
def build_enc_midwall_dbifold(w=1.20, d=0.90, h=1.90): _midwall_enclosure(w, d, h, 'double-bifold')
def build_enc_midwall_open(w=1.20, d=0.90, h=1.90): _midwall_enclosure(w, d, h, 'open')


def _door_only(w, h, door):
    """Door-only: two wall posts + door between (no side glass)."""
    ch = m_chrome()
    cyl('post_l', ch, 0.025, h, (-w / 2, -0.02, h / 2))
    cyl('post_r', ch, 0.025, h, (w / 2, -0.02, h / 2))
    box('rail', ch, (w + 0.06, 0.04, 0.04), (0, -0.02, h + 0.02))
    if door == 'sliding':
        _glass_panel('door_fixed', w * 0.5, h - 0.04, 0.008, loc=(-w * 0.24, -0.02, h / 2))
        _glass_panel('door_slide', w * 0.52, h - 0.04, 0.008, loc=(w * 0.2, -0.05, h / 2))
        box('handle', ch, (0.02, 0.03, 0.3), (w * 0.38, -0.08, h * 0.5))
    elif door == 'bifold':
        _front_bifold(w, 0.04, h, double=False)
    else:  # gap: just a header rail, no glass
        pass


def build_enc_dooronly_sliding(w=0.90, h=1.90): _door_only(w, h, 'sliding')
def build_enc_dooronly_bifold(w=0.90, h=1.90): _door_only(w, h, 'bifold')
def build_enc_dooronly_gap(w=0.90, h=1.90): _door_only(w, h, 'gap')


# =====================================================================
# TRAYS (3) — corner radius + drain position are per-build params
# =====================================================================

def _tray(w, d, h, corner_r=0.0, drain='center'):
    if corner_r > 0:
        r = corner_r
        box('tray_back', m_stone(), (w, d - r, h), (0, -(d - r) / 2, h / 2), bevel=0.008)
        box('tray_side', m_stone(), (w - r, r, h), (-r / 2, -(d - r) - r / 2, h / 2), bevel=0.008)
        quarter_disc('tray_corner', m_stone(), r, h, center=(w / 2 - r, -(d - r)))
    else:
        box('tray', m_stone(), (w, d, h), (0, -d / 2, h / 2), bevel=0.01)
    # recessed top
    box('recess', m_stone(), (w - 0.07, d - 0.07, 0.008), (0, -d / 2, h - 0.003))
    # drain
    if drain == 'corner':
        dx, dy = w / 2 - 0.12, -d + 0.12
    elif drain == 'edge':
        dx, dy = 0, -d + 0.10
    else:
        dx, dy = 0, -d / 2
    cyl('waste', m_waste(), 0.045, 0.018, (dx, dy, h + 0.004))


def build_tray_square(w=0.90, h=0.045, d=0.90): _tray(w, d, h, corner_r=0.0, drain='center')
def build_tray_rect(w=1.20, h=0.045, d=0.80): _tray(w, d, h, corner_r=0.0, drain='center')
def build_tray_quadrant(w=0.90, h=0.045, d=0.90): _tray(w, d, h, corner_r=min(w, d) * 0.95, drain='corner')


# =====================================================================
# TOILETS (6)
# =====================================================================

def _toilet_base(w, d, pan_h):
    box('pan', m_ceramic(), (w, d, pan_h), (0, -d / 2, pan_h / 2), bevel=0.015)
    prof = [(0.001, 0.0), (0.10, 0.03), (0.15, 0.09), (0.17, 0.15), (0.16, 0.21), (0.13, 0.26), (0.16, 0.29)]
    bowl = lathe('bowl', m_ceramic(), prof, axis='Z', steps=36)
    bowl.location = (0, -d * 0.72, pan_h)
    tor = None
    import math as _m
    # seat ring
    bpy.ops.mesh.primitive_torus_add(major_radius=0.155, minor_radius=0.02,
                                     location=(0, -d * 0.72, pan_h + 0.29))
    _add(bpy.context.view_layer.objects.active, 'seat', m_ceramic())
    box('lid', m_ceramic(), (0.32, 0.32, 0.016), (0, -d * 0.72, pan_h + 0.315))


def build_toilet_close_coupled(w=0.36, h=0.78, d=0.66):
    _toilet_base(w, d, 0.40)
    box('cistern', m_ceramic(), (w, 0.18, 0.36), (0, -0.09, 0.58), bevel=0.012)
    box('cistern_lid', m_ceramic(), (w + 0.02, 0.20, 0.02), (0, -0.09, 0.77))
    cyl('flush', m_chrome(), 0.025, 0.012, (0, -0.09, 0.785))


def build_toilet_btw(w=0.36, h=0.80, d=0.52):
    _toilet_base(w, d, 0.40)
    box('cistern_slab', m_ceramic(), (w, 0.10, 0.40), (0, -0.05, 0.60), bevel=0.01)
    box('flush_plate', m_chrome(), (0.14, 0.008, 0.09), (0, -0.105, 0.72))


def build_toilet_wall_hung(w=0.36, h=0.36, d=0.54):
    """Wall-hung: floating pan, origin at back-bottom of the pan (mount height set in editor)."""
    box('pan', m_ceramic(), (w, d, 0.30), (0, -d / 2, 0.20), bevel=0.02)
    prof = [(0.001, 0.0), (0.10, 0.02), (0.15, 0.07), (0.16, 0.12), (0.14, 0.16), (0.15, 0.18)]
    bowl = lathe('bowl', m_ceramic(), prof, axis='Z', steps=36)
    bowl.location = (0, -d * 0.68, 0.34)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.14, minor_radius=0.018,
                                     location=(0, -d * 0.68, 0.52))
    _add(bpy.context.view_layer.objects.active, 'seat', m_ceramic())
    box('lid', m_ceramic(), (0.30, 0.30, 0.015), (0, -d * 0.68, 0.545))


def build_toilet_comfort(w=0.36, h=0.85, d=0.66):
    _toilet_base(w, d, 0.46)
    box('cistern', m_ceramic(), (w, 0.18, 0.36), (0, -0.09, 0.64), bevel=0.012)
    box('cistern_lid', m_ceramic(), (w + 0.02, 0.20, 0.02), (0, -0.09, 0.83))


def build_toilet_compact(w=0.36, h=0.75, d=0.48):
    _toilet_base(w, d, 0.38)
    box('cistern', m_ceramic(), (w, 0.14, 0.34), (0, -0.07, 0.55), bevel=0.012)
    box('cistern_lid', m_ceramic(), (w + 0.02, 0.16, 0.02), (0, -0.07, 0.73))


def build_toilet_bidet(w=0.36, h=0.80, d=0.54):
    cyl('pedestal', m_ceramic(), 0.07, 0.34, (0, -d * 0.45, 0.17))
    bowl = lathe('bowl', m_ceramic(),
                 [(0.001, 0.0), (0.11, 0.02), (0.16, 0.06), (0.17, 0.12), (0.16, 0.18), (0.17, 0.20)],
                 axis='Z', steps=36)
    bowl.location = (0, -d * 0.45, 0.34)
    bowl.scale = (1, 1.3, 1)
    bpy.ops.object.transform_apply(scale=True)
    cyl('tap_body', m_chrome(), 0.012, 0.09, (0, -0.08, 0.56))
    cyl('tap_spout', m_chrome(), 0.008, 0.07, (0, -0.12, 0.60), rot=(math.pi / 2, 0, 0))


# =====================================================================
# BASINS (6)
# =====================================================================

def _basin_bowl(w, d, bh, y):
    prof = [(0.001, 0.0), (min(w, d) * 0.22, 0.02), (min(w, d) * 0.42, bh * 0.55),
            (min(w, d) * 0.47, bh * 0.9), (min(w, d) * 0.44, bh)]
    bowl = lathe('bowl', m_ceramic(), prof, axis='Z', steps=40)
    bowl.location = (0, y, 0)
    bowl.scale = (w / (min(w, d) * 0.94), d / (min(w, d) * 0.94), 1)
    bpy.ops.object.transform_apply(scale=True)
    return bowl


def build_basin_pedestal(w=0.56, h=0.82, d=0.46):
    col = cyl('pedestal', m_ceramic(), 0.075, h - 0.30, (0, -d * 0.35, (h - 0.30) / 2))
    col.scale = (1, 0.8, 1)
    bpy.ops.object.transform_apply(scale=True)
    cyl('base', m_ceramic(), 0.11, 0.02, (0, -d * 0.35, 0.01))
    _basin_bowl(w, d, 0.18, -d * 0.35)
    bpy.context.view_layer.objects.active.location.z = h - 0.18 if False else 0
    # raise bowl to pedestal top
    for o in bpy.data.objects:
        if o.name == 'bowl':
            o.location.z = h - 0.18


def build_basin_wall_hung(w=0.60, h=0.16, d=0.42):
    _basin_bowl(w, d, h, -d * 0.4)
    box('backplate', m_ceramic(), (w, 0.025, h + 0.05), (0, -0.0125, (h + 0.05) / 2))


def build_basin_countertop_round(w=0.40, h=0.14, d=0.40):
    bowl = lathe('bowl', m_ceramic(),
                 [(0.001, 0.0), (w * 0.28, 0.01), (w * 0.46, h * 0.6), (w * 0.48, h)],
                 axis='Z', steps=44)
    return bowl


def build_basin_countertop_rect(w=0.55, h=0.12, d=0.38):
    o = box('bowl', m_ceramic(), (w, d, h), (0, -d / 2, h / 2), bevel=0.02)
    delete_top_faces(o)
    box('ifloor', m_ceramic(), (w - 0.05, d - 0.05, 0.012), (0, -d / 2, 0.02))


def build_basin_semi_recessed(w=0.55, h=0.17, d=0.44):
    box('counter', m_mdf(), (w + 0.1, d * 0.55, 0.03), (0, -d * 0.275, 0.015))
    bowl = _basin_bowl(w, d, h, -d * 0.55)
    bowl.location.y = -d * 0.55
    for o in bpy.data.objects:
        if o.name == 'bowl':
            o.location.z = -h * 0.35


def build_basin_cloakroom(w=0.40, h=0.14, d=0.30):
    _basin_bowl(w, d, h, -d * 0.42)
    box('backplate', m_ceramic(), (w, 0.02, h + 0.04), (0, -0.01, (h + 0.04) / 2))


# =====================================================================
# VANITY (8)
# =====================================================================

def _vanity_body(w, h, d, floating, drawers, cupboard, curved=False):
    body_h = h - 0.05
    z0 = 0.12 if floating else 0.0
    bm = m_oak()
    if curved:
        body = cyl('body', bm, 0.5, body_h, (0, -d / 2, z0 + body_h / 2))
        body.scale = (w, d, 1)
        bpy.ops.object.transform_apply(scale=True)
    else:
        box('body', bm, (w, d, body_h), (0, -d / 2, z0 + body_h / 2), bevel=0.004)
    if floating:
        box('shadow_gap', m_gap(), (w - 0.06, d - 0.04, 0.02), (0, -d / 2, 0.06))
    # fronts
    n_rows = max(drawers, 1) if drawers else 1
    row_h = (body_h - 0.04) / (n_rows + (1 if cupboard else 0))
    for i in range(drawers):
        zc = z0 + body_h - 0.02 - row_h * (i + 0.5)
        box(f'drawer_{i}', bm, (w - 0.05, 0.018, row_h - 0.015), (0, -d - 0.001 + 0.01, zc))
        box(f'handle_{i}', m_chrome(), (w * 0.35, 0.012, 0.012), (0, -d - 0.02, zc + row_h * 0.25))
    if cupboard:
        zc = z0 + (row_h if drawers else body_h / 2) / 1 + (row_h * drawers if drawers else 0)
        zc = z0 + (body_h - (row_h * drawers)) / 2
        box('door_l', bm, (w / 2 - 0.03, 0.018, body_h - row_h * drawers - 0.03),
            (-w / 4, -d + 0.009, z0 + (body_h - row_h * drawers) / 2))
        box('door_r', bm, (w / 2 - 0.03, 0.018, body_h - row_h * drawers - 0.03),
            (w / 4, -d + 0.009, z0 + (body_h - row_h * drawers) / 2))
        box('handle_l', m_chrome(), (0.012, 0.012, 0.16), (-0.03, -d - 0.01, z0 + (body_h - row_h * drawers) / 2))
        box('handle_r', m_chrome(), (0.012, 0.012, 0.16), (0.03, -d - 0.01, z0 + (body_h - row_h * drawers) / 2))
    # worktop + basin
    box('worktop', mat('worktop_white', (0.93, 0.92, 0.90), 0, 0.3), (w + 0.02, d + 0.01, 0.03),
        (0, -d / 2, h - 0.015))
    _basin_bowl(min(w * 0.7, 0.46), min(d * 0.8, 0.36), 0.11, -d * 0.55)
    for o in bpy.data.objects:
        if o.name == 'bowl':
            o.location.z = h + 0.0


def build_vanity_standing_drawers(w=0.60, h=0.85, d=0.46): _vanity_body(w, h, d, False, 2, False)
def build_vanity_standing_cupboard(w=0.60, h=0.85, d=0.46): _vanity_body(w, h, d, False, 0, True)
def build_vanity_standing_mix(w=0.80, h=0.85, d=0.46): _vanity_body(w, h, d, False, 1, True)
def build_vanity_floating_drawers(w=0.60, h=0.60, d=0.46): _vanity_body(w, h, d, True, 2, False)
def build_vanity_floating_cupboard(w=0.60, h=0.60, d=0.46): _vanity_body(w, h, d, True, 0, True)
def build_vanity_curved(w=0.60, h=0.85, d=0.46): _vanity_body(w, h, d, False, 2, False, curved=True)


def build_vanity_combined_btw(w=1.20, h=0.85, d=0.46):
    """Combined toilet+basin vanity: BTW toilet on the left, basin vanity right, shared top."""
    box('body', m_mdf(), (w, d, h - 0.05), (0, -d / 2, (h - 0.05) / 2), bevel=0.003)
    box('worktop', mat('worktop_white', (0.93, 0.92, 0.90), 0, 0.3), (w + 0.02, d + 0.01, 0.03),
        (0, -d / 2, h - 0.015))
    # toilet section (left): BTW pan on the floor in front of the unit
    _toilet_base(0.36, 0.50, 0.40)
    for o in bpy.data.objects:
        if o.name in ('pan', 'bowl', 'seat', 'lid'):
            o.location.x = -w / 2 + 0.25
    box('cistern_slab', m_ceramic(), (0.36, 0.10, 0.42), (-w / 2 + 0.25, -0.05, 0.62), bevel=0.01)
    # basin section (right)
    _basin_bowl(0.42, 0.34, 0.11, -d * 0.55)
    for o in bpy.data.objects:
        if o.name == 'bowl':
            o.location.x = w / 2 - 0.30
            o.location.z = h + 0.0
    box('drawer_0', m_mdf(), (w * 0.4, 0.018, 0.20), (w * 0.25, -d + 0.009, h * 0.55))
    box('handle_0', m_chrome(), (w * 0.2, 0.012, 0.012), (w * 0.25, -d - 0.012, h * 0.62))


def build_vanity_basin_on_top(w=0.60, h=0.85, d=0.46):
    """Cupboard unit + separate countertop vessel basin."""
    box('body', m_oak(), (w, d, h - 0.12), (0, -d / 2, (h - 0.12) / 2), bevel=0.004)
    box('door_l', m_oak(), (w / 2 - 0.03, 0.018, h - 0.16), (-w / 4, -d + 0.009, (h - 0.12) / 2))
    box('door_r', m_oak(), (w / 2 - 0.03, 0.018, h - 0.16), (w / 4, -d + 0.009, (h - 0.12) / 2))
    box('top', mat('worktop_white', (0.93, 0.92, 0.90), 0, 0.3), (w + 0.02, d + 0.01, 0.025),
        (0, -d / 2, h - 0.10))
    bowl = lathe('vessel', m_ceramic(),
                 [(0.001, 0.0), (0.10, 0.01), (0.17, 0.08), (0.19, 0.13)],
                 axis='Z', steps=44)
    bowl.location = (0, -d * 0.5, h - 0.085)


# =====================================================================
# MIRRORS (10)
# =====================================================================

def _mirror_face(w, h, shape):
    if shape == 'round':
        cyl('face', m_mirror(), w / 2, 0.012, (0, -0.006, h / 2), rot=(math.pi / 2, 0, 0))
    elif shape == 'oval':
        o = cyl('face', m_mirror(), 0.5, 0.012, (0, -0.006, h / 2), rot=(math.pi / 2, 0, 0))
        o.scale = (w, h, 1)
        bpy.ops.object.transform_apply(scale=True)
    else:
        box('face', m_mirror(), (w, 0.012, h), (0, -0.006, h / 2))


def _led_border(w, h, shape, margin):
    if shape in ('round', 'oval'):
        r = w / 2 - (0.03 if margin else 0.005)
        bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=0.008,
                                         location=(0, -0.014, h / 2), rotation=(math.pi / 2, 0, 0))
        t = _add(bpy.context.view_layer.objects.active, 'led', m_led())
        if shape == 'oval':
            t.scale = (1, h / w, 1)
            bpy.ops.object.transform_apply(scale=True)
    else:
        iw, ih = (w - 0.09, h - 0.09) if margin else (w - 0.02, h - 0.02)
        bt = 0.012
        box('led_t', m_led(), (iw, 0.01, bt), (0, -0.016, h - bt / 2))
        box('led_b', m_led(), (iw, 0.01, bt), (0, -0.016, bt / 2))
        box('led_l', m_led(), (bt, 0.01, ih), (-iw / 2 + bt / 2, -0.016, h / 2))
        box('led_r', m_led(), (bt, 0.01, ih), (iw / 2 - bt / 2, -0.016, h / 2))


def build_mirror_rect(w=0.60, h=0.80): 
    box('back', m_black(), (w, 0.02, h), (0, -0.01, h / 2))
    _mirror_face(w, h, 'rect')
def build_mirror_rect_led(w=0.60, h=0.80):
    box('back', m_black(), (w, 0.02, h), (0, -0.01, h / 2))
    _mirror_face(w, h, 'rect'); _led_border(w, h, 'rect', margin=False)
def build_mirror_round(w=0.60, h=0.60):
    cyl('back', m_black(), w / 2, 0.02, (0, -0.01, h / 2), rot=(math.pi / 2, 0, 0))
    _mirror_face(w, h, 'round')
def build_mirror_round_led(w=0.60, h=0.60):
    cyl('back', m_black(), w / 2, 0.02, (0, -0.01, h / 2), rot=(math.pi / 2, 0, 0))
    _mirror_face(w, h, 'round'); _led_border(w, h, 'round', margin=True)
def build_mirror_oval(w=0.50, h=0.80):
    o = cyl('back', m_black(), 0.5, 0.02, (0, -0.01, h / 2), rot=(math.pi / 2, 0, 0))
    o.scale = (w, h, 1)
    bpy.ops.object.transform_apply(scale=True)
    _mirror_face(w, h, 'oval')
def build_mirror_oval_led(w=0.50, h=0.80):
    o = cyl('back', m_black(), 0.5, 0.02, (0, -0.01, h / 2), rot=(math.pi / 2, 0, 0))
    o.scale = (w, h, 1)
    bpy.ops.object.transform_apply(scale=True)
    _mirror_face(w, h, 'oval'); _led_border(w, h, 'oval', margin=True)


def _cabinet(w, h, d, doors):
    box('body', m_mdf(), (w, d, h), (0, -d / 2, h / 2))
    dw = w / doors
    for i in range(doors):
        x = -w / 2 + dw * (i + 0.5)
        box(f'door_{i}', m_mdf(), (dw - 0.015, 0.016, h - 0.03), (x, -d - 0.008, h / 2))
        hx = x + dw / 2 - 0.03 if i % 2 == 0 else x - dw / 2 + 0.03
        box(f'handle_{i}', m_chrome(), (0.01, 0.012, 0.12), (hx, -d - 0.02, h * 0.55))
    # mirrored door fronts
    for i in range(doors):
        x = -w / 2 + dw * (i + 0.5)
        box(f'mirror_{i}', m_mirror(), (dw - 0.04, 0.004, h - 0.08), (x, -d - 0.018, h / 2))


def build_cabinet_1door(w=0.45, h=0.70, d=0.14): _cabinet(w, h, d, 1)
def build_cabinet_2door(w=0.60, h=0.70, d=0.14): _cabinet(w, h, d, 2)
def build_cabinet_3door(w=0.90, h=0.70, d=0.14): _cabinet(w, h, d, 3)
def build_cabinet_4door(w=1.20, h=0.70, d=0.14): _cabinet(w, h, d, 4)


# =====================================================================
# PANEL (1) + TAPS/SHOWERS (4)
# =====================================================================

def build_panel_board(w=2.40, h=1.20, d=0.009):
    box('panel', mat('panel_board', (0.93, 0.92, 0.90), 0, 0.62), (w, d, h), (w / 2, -d / 2, h / 2))


def build_tap_basin_mono():
    cyl('base', m_chrome(), 0.024, 0.02, (0, 0, 0.01))
    cyl('body', m_chrome(), 0.016, 0.14, (0, -0.01, 0.09))
    cyl('spout', m_chrome(), 0.011, 0.13, (0, -0.075, 0.155), rot=(math.pi / 2, 0, 0))
    cyl('spout_drop', m_chrome(), 0.011, 0.05, (0, -0.14, 0.13))
    cyl('lever', m_chrome(), 0.007, 0.07, (0, -0.005, 0.18), rot=(0, 0, math.radians(-20)))


def build_tap_bath_filler():
    for x in (-0.075, 0.075):
        cyl('leg', m_chrome(), 0.013, 0.10, (x, 0, 0.05))
        cyl('body', m_chrome(), 0.016, 0.05, (x, 0, 0.115))
        cyl('cross_top', m_chrome(), 0.022, 0.014, (x, 0, 0.145))
    cyl('bridge', m_chrome(), 0.011, 0.16, (0, 0, 0.135), rot=(0, 0, math.pi / 2))
    cyl('spout', m_chrome(), 0.012, 0.09, (0, -0.045, 0.10), rot=(math.pi / 2, 0, 0))


def build_shower_head_fixed():
    cyl('flange', m_chrome(), 0.022, 0.012, (0, 0.006, 0.16))
    cyl('arm', m_chrome(), 0.012, 0.24, (0, -0.11, 0.16), rot=(math.pi / 2, 0, 0))
    cyl('head', m_chrome(), 0.10, 0.035, (0, -0.23, 0.155))
    cyl('face', mat('shower_face', (0.9, 0.9, 0.9), 0, 0.4), 0.088, 0.006, (0, -0.23, 0.136))


def build_shower_set_bar():
    box('valve', m_chrome(), (0.16, 0.08, 0.18), (0, -0.05, 0.55))
    cyl('knob_l', m_chrome(), 0.03, 0.03, (-0.055, -0.10, 0.55), rot=(math.pi / 2, 0, 0))
    cyl('knob_r', m_chrome(), 0.03, 0.03, (0.055, -0.10, 0.55), rot=(math.pi / 2, 0, 0))
    cyl('rail', m_chrome(), 0.011, 0.65, (0.14, -0.02, 0.75))
    cyl('rail_fix_b', m_chrome(), 0.016, 0.03, (0.14, 0.005, 0.48))
    cyl('rail_fix_t', m_chrome(), 0.016, 0.03, (0.14, 0.005, 1.02))
    cyl('holder', m_chrome(), 0.02, 0.05, (0.14, -0.05, 0.88), rot=(math.pi / 2, 0, 0))
    hs = cyl('handset', m_chrome(), 0.024, 0.18, (0.10, -0.13, 0.78))
    hs.rotation_euler = (0, math.radians(20), 0)
    cyl('arm', m_chrome(), 0.012, 0.30, (0, -0.08, 1.20), rot=(math.radians(80), 0, 0))
    cyl('head', m_chrome(), 0.08, 0.04, (0.02, -0.30, 1.26))


# =====================================================================
# HEATING (6)
# =====================================================================

def build_radiator_panel(w=1.20, h=0.60, d=0.10):
    """Convector panel radiator: 2 panels + convector fins between."""
    n_fins = max(8, int(w / 0.05))
    box('panel_f', m_white(), (w, d * 0.28, h), (0, -d * 0.72, h / 2), bevel=0.012)
    box('panel_b', m_white(), (w, d * 0.28, h), (0, -d * 0.28, h / 2), bevel=0.012)
    for i in range(n_fins):
        x = -w / 2 + (i + 0.5) * (w / n_fins)
        box(f'fin_{i}', m_white(), (0.006, d * 0.44, h - 0.08), (x, -d / 2, h / 2))
    box('top_grille', m_white(), (w, d, 0.015), (0, -d / 2, h + 0.007))
    for x in (-w / 2 + 0.08, w / 2 - 0.08):
        cyl('conn', m_chrome(), 0.012, 0.05, (x, -d / 2, 0.04), rot=(math.pi / 2, 0, 0))


def build_radiator_flat_finned(w=1.20, h=0.60, d=0.08):
    """Flat aluminium radiator: smooth front + vertical section ridges."""
    box('body', m_white(), (w, d, h), (0, -d / 2, h / 2), bevel=0.015)
    n = max(6, int(w / 0.12))
    for i in range(n + 1):
        x = -w / 2 + i * (w / n)
        box(f'ridge_{i}', m_white(), (0.014, d + 0.012, h - 0.04), (x, -d / 2, h / 2))


def build_radiator_column(w=1.00, h=0.60, d=0.10, cols=2):
    """Column radiator: N vertical tubes in pairs + top/bottom headers."""
    n_sections = max(6, int(w / 0.05))
    sec_w = w / n_sections
    col_r = min(0.021, sec_w * 0.42)
    spacing = d * 0.5
    for i in range(n_sections):
        x = -w / 2 + sec_w * (i + 0.5)
        for k in range(cols):
            y = -(d / 2) + (k - (cols - 1) / 2) * spacing
            cyl(f'col_{i}_{k}', m_white(), col_r, h - 0.09, (x, y, h / 2))
    for z in (0.028, h - 0.028):
        box(f'header_{z}', m_white(), (w, d * 0.72, 0.055), (0, -d / 2, z))


def _ladder_rail(w, h, bar_shape='round', grouped=True, floor_stand=False,
                 bar_r=0.011, bar_face=0.045, bar_depth=0.018, standoff=0.05):
    coll_r = 0.015
    n_bars = max(6, int(h / 0.085))
    if grouped:
        # split into clusters of 3-4 with larger gaps
        clusters, rem = [], n_bars
        while rem > 0:
            take = 4 if rem >= 7 else rem
            clusters.append(take)
            rem -= take
    else:
        clusters = [n_bars]
    bar_gap = 0.028 if not grouped else 0.014
    cluster_gap = 0.075
    total = sum(clusters) * bar_face + (sum(clusters) - len(clusters)) * bar_gap + (len(clusters) - 1) * cluster_gap
    bottom = (h - total) / 2
    coll_axis_y = -(standoff + coll_r)
    for i, sx in enumerate((-1, 1)):
        cyl(f'collector_{i}', m_chrome(), coll_r, h, (sx * (w / 2 - coll_r), coll_axis_y, h / 2))
    z = bottom
    bi = 0
    for nb in clusters:
        for _ in range(nb):
            if bar_shape == 'round':
                cyl(f'bar_{bi}', m_chrome(), bar_r, w, (0, coll_axis_y, z + bar_r), rot=(0, 0, math.pi / 2))
                z += bar_r * 2 + bar_gap
            else:
                o = box(f'bar_{bi}', m_chrome(), (w, bar_depth, bar_face), (0, coll_axis_y, z + bar_face / 2))
                md = o.modifiers.new('B', 'BEVEL')
                md.width = 0.005
                md.segments = 2
                md.limit_method = 'ANGLE'
                md.angle_limit = math.radians(30)
                z += bar_face + bar_gap
            bi += 1
        z += cluster_gap - bar_gap
    if floor_stand:
        for sx in (-1, 1):
            box(f'leg_{sx}', m_chrome(), (0.03, standoff + 0.06, 0.05), (sx * (w / 2 - 0.05), coll_axis_y - 0.02, 0.025))
            cyl(f'foot_{sx}', m_chrome(), 0.02, 0.12, (sx * (w / 2 - 0.05), coll_axis_y - 0.05, 0.03), rot=(math.pi / 2, 0, 0))


def build_rail_round(w=0.50, h=1.10): _ladder_rail(w, h, 'round', grouped=True)
def build_rail_square(w=0.50, h=1.10): _ladder_rail(w, h, 'square', grouped=True)
def build_rail_floor(w=0.50, h=1.10): _ladder_rail(w, h, 'round', grouped=False, floor_stand=True)


# =====================================================================
# REGISTRY + ENTRY POINT
# =====================================================================

BUILDERS = {
    # baths (17)
    'bath-se-rect-rect': build_bath_se_rect_rect,
    'bath-se-rect-round': build_bath_se_rect_round,
    'bath-se-asym': build_bath_se_asym,
    'bath-de-rect-rect': build_bath_de_rect_rect,
    'bath-de-rect-round': build_bath_de_rect_round,
    'bath-btw-dshape': build_bath_btw_dshape,
    'bath-btw-left': build_bath_btw_left,
    'bath-btw-right': build_bath_btw_right,
    'bath-btw-caversham': build_bath_btw_caversham,
    'bath-corner-generic': build_bath_corner_generic,
    'bath-corner-whitchurch': build_bath_corner_whitchurch,
    'bath-fs-plinth': build_bath_fs_plinth,
    'bath-fs-feet': build_bath_fs_feet,
    'bath-fs-slipper': build_bath_fs_slipper,
    'bath-fs-round': build_bath_fs_round,
    'bath-fs-boat': build_bath_fs_boat,
    'bath-p-shape': build_bath_p_shape,
    'bath-l-shape': build_bath_l_shape,
    # screens (6)
    'screen-static-square': build_screen_static_square,
    'screen-static-rounded': build_screen_static_rounded,
    'screen-hinged': build_screen_hinged,
    'screen-curved': build_screen_curved,
    'screen-sliding-straight': build_screen_sliding_straight,
    'screen-sliding-curved': build_screen_sliding_curved,
    # enclosures (14)
    'enc-corner-sq-sliding': build_enc_corner_sq_sliding,
    'enc-corner-sq-dsliding': build_enc_corner_sq_dsliding,
    'enc-corner-sq-bifold': build_enc_corner_sq_bifold,
    'enc-corner-sq-open': build_enc_corner_sq_open,
    'enc-corner-sq-panel': build_enc_corner_sq_panel,
    'enc-quadrant-sliding': build_enc_quadrant_sliding,
    'enc-quadrant-bifold': build_enc_quadrant_bifold,
    'enc-quadrant-open': build_enc_quadrant_open,
    'enc-midwall-sliding': build_enc_midwall_sliding,
    'enc-midwall-dbifold': build_enc_midwall_dbifold,
    'enc-midwall-open': build_enc_midwall_open,
    'enc-dooronly-sliding': build_enc_dooronly_sliding,
    'enc-dooronly-bifold': build_enc_dooronly_bifold,
    'enc-dooronly-gap': build_enc_dooronly_gap,
    # trays (3)
    'tray-square': build_tray_square,
    'tray-rect': build_tray_rect,
    'tray-quadrant': build_tray_quadrant,
    # toilets (6)
    'toilet-close-coupled': build_toilet_close_coupled,
    'toilet-btw': build_toilet_btw,
    'toilet-wall-hung': build_toilet_wall_hung,
    'toilet-comfort': build_toilet_comfort,
    'toilet-compact': build_toilet_compact,
    'toilet-bidet': build_toilet_bidet,
    # basins (6)
    'basin-pedestal': build_basin_pedestal,
    'basin-wall-hung': build_basin_wall_hung,
    'basin-countertop-round': build_basin_countertop_round,
    'basin-countertop-rect': build_basin_countertop_rect,
    'basin-semi-recessed': build_basin_semi_recessed,
    'basin-cloakroom': build_basin_cloakroom,
    # vanity (8)
    'vanity-standing-drawers': build_vanity_standing_drawers,
    'vanity-standing-cupboard': build_vanity_standing_cupboard,
    'vanity-standing-mix': build_vanity_standing_mix,
    'vanity-floating-drawers': build_vanity_floating_drawers,
    'vanity-floating-cupboard': build_vanity_floating_cupboard,
    'vanity-curved': build_vanity_curved,
    'vanity-combined-btw': build_vanity_combined_btw,
    'vanity-basin-on-top': build_vanity_basin_on_top,
    # mirrors (10)
    'mirror-rect': build_mirror_rect,
    'mirror-rect-led': build_mirror_rect_led,
    'mirror-round': build_mirror_round,
    'mirror-round-led': build_mirror_round_led,
    'mirror-oval': build_mirror_oval,
    'mirror-oval-led': build_mirror_oval_led,
    'cabinet-1door': build_cabinet_1door,
    'cabinet-2door': build_cabinet_2door,
    'cabinet-3door': build_cabinet_3door,
    'cabinet-4door': build_cabinet_4door,
    # panel + taps (5)
    'panel-board': build_panel_board,
    'tap-basin-mono': build_tap_basin_mono,
    'tap-bath-filler': build_tap_bath_filler,
    'shower-head-fixed': build_shower_head_fixed,
    'shower-set-bar': build_shower_set_bar,
    # heating (6)
    'radiator-panel': build_radiator_panel,
    'radiator-flat-finned': build_radiator_flat_finned,
    'radiator-column': build_radiator_column,
    'rail-round': build_rail_round,
    'rail-square': build_rail_square,
    'rail-floor': build_rail_floor,
}


def build_one(slug, qa=True):
    """Clean scene, build archetype, set origin, export GLB, render thumb (+QA)."""
    if slug not in BUILDERS:
        print(f"UNKNOWN {slug}")
        return
    _clean()
    BUILDERS[slug]()
    obj = set_origin_back_bottom_center()
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    glb = export_glb(slug)
    polys = len(obj.data.polygons)
    render_thumb(slug)
    if qa:
        render_qa(slug)
    print(f"DONE {slug} dims=({(max(xs)-min(xs))*1000:.0f}w {(max(ys)-min(ys))*1000:.0f}d "
          f"{(max(zs)-min(zs))*1000:.0f}h mm) polys={polys}")

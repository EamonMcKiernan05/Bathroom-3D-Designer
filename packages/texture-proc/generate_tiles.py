"""Generate a starter texture library with PIL.

Each texture is rendered at its real tile aspect ratio, grout baked in,
with a normal map (emboss) + 256px preview. Outputs to assets/textures/<category>/<slug>/
and writes assets/textures/manifest.json for the DB seed.

Run:  python generate_tiles.py   (needs: pip install pillow)
"""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "assets" / "textures"
MANIFEST = []


def _base_img(w, h, color=(240, 240, 240)):
    return Image.new("RGB", (w, h), color)


def _noise(img, amount=5, seed=42):
    rnd = random.Random(seed)
    px = img.load()
    w, h = img.size
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            d = rnd.randint(-amount, amount)
            px[x, y] = (max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d)))
    return img


def _draw_grout(img, tile_w, tile_h, grout_px, grout_color=(196, 196, 196)):
    """Draw grout lines over an existing full-bleed pattern image."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    x = 0
    while x < w:
        draw.rectangle([x, 0, min(x + grout_px, w), h], fill=grout_color)
        x += tile_w + grout_px
    y = 0
    while y < h:
        draw.rectangle([0, y, w, min(y + grout_px, h)], fill=grout_color)
        y += tile_h + grout_px
    return img


def _marble(img, seed=7, veins=16, width_range=(2, 6), alpha_range=(60, 130), tone=(110, 116, 130)):
    """Smooth S-curve marble veins, full bleed."""
    rnd = random.Random(seed)
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for _ in range(veins):
        x0 = rnd.randint(-w // 3, w)
        y0 = rnd.randint(-h // 3, h + h // 3)
        segs = rnd.randint(3, 6)
        x = x0
        y = y0
        pts = [(x0, y0)]
        for _s in range(segs):
            tx = x + rnd.randint(w // 4, w // 2)
            ty = y + rnd.randint(-h // 3, h // 3)
            # interpolate gentle curve
            n = 22
            for i in range(1, n + 1):
                t = i / n
                px = x + (tx - x) * t
                py = y + (ty - y) * t + rnd.randint(-8, 8) * math.sin(math.pi * t)
                pts.append((px, py))
            x, y = tx, ty
        width = rnd.randint(*width_range)
        r = tone[0] + rnd.randint(-12, 12)
        g = tone[1] + rnd.randint(-12, 12)
        b = tone[2] + rnd.randint(-14, 14)
        draw.line(pts, fill=(max(0, r), max(0, g), max(0, b), rnd.randint(*alpha_range)), width=width, joint="curve")
    overlay = overlay.filter(ImageFilter.GaussianBlur(0.8))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _wood_grain(img, seed=11, planks=5):
    rnd = random.Random(seed)
    w, h = img.size
    draw = ImageDraw.Draw(img)
    base_r, base_g, base_b = img.getpixel((w // 2, h // 2))
    for p in range(planks):
        y0 = (h // planks) * p
        y1 = (h // planks) * (p + 1)
        shade = rnd.randint(-12, 12)
        draw.rectangle([0, y0, w, y1], fill=(
            max(0, min(255, base_r + shade)),
            max(0, min(255, base_g + shade)),
            max(0, min(255, base_b + shade)),
        ))
        for _ in range(rnd.randint(8, 14)):
            gy = rnd.randint(y0 + 2, y1 - 2)
            step = 10
            pts = []
            for x in range(0, w + step, step):
                yy = gy + int(rnd.randint(-6, 6) * math.sin(x / rnd.randint(40, 110) + rnd.random() * 6))
                pts.append((x, yy))
            draw.line(pts, fill=(
                max(0, min(255, base_r - 28 + rnd.randint(-6, 6))),
                max(0, min(255, base_g - 22 + rnd.randint(-6, 6))),
                max(0, min(255, base_b - 16 + rnd.randint(-6, 6))),
            ), width=rnd.randint(1, 2))
        if p > 0:
            draw.line([(0, y0), (w, y0)], fill=(58, 40, 26), width=2)
    return img


def _terrazzo(img, seed=5, flecks=1100):
    rnd = random.Random(seed)
    w, h = img.size
    px = img.load()
    palette = [(40, 40, 40), (120, 60, 40), (60, 90, 140), (150, 120, 60), (90, 120, 90), (180, 180, 190), (160, 70, 70)]
    for _ in range(flecks):
        x = rnd.randint(0, w - 1)
        y = rnd.randint(0, h - 1)
        c = rnd.choice(palette)
        r = rnd.randint(1, 3)
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h:
                    px[xx, yy] = c
    return img


def _stone_texture(img, seed=13):
    """Speckled natural stone."""
    rnd = random.Random(seed)
    w, h = img.size
    px = img.load()
    base = img.getpixel((w // 2, h // 2))
    for _ in range(2600):
        x = rnd.randint(0, w - 1)
        y = rnd.randint(0, h - 1)
        d = rnd.randint(-22, 22)
        px[x, y] = (
            max(0, min(255, base[0] + d)),
            max(0, min(255, base[1] + d)),
            max(0, min(255, base[2] + d)),
        )
    return img


def _mosaic(w, h, grid=6, base_palette=None, grout=(196, 196, 196)):
    """Small square mosaic — one 'tile' image contains grid x grid cells."""
    img = _base_img(w, h)
    draw = ImageDraw.Draw(img)
    cell = w // grid
    grout_px = max(2, cell // 8)
    rnd = random.Random(3)
    palette = base_palette or [(245, 245, 245), (236, 236, 236), (250, 250, 250)]
    draw.rectangle([0, 0, w - 1, h - 1], fill=grout)
    for gy in range(grid):
        for gx in range(grid):
            x0 = gx * cell + grout_px // 2
            y0 = gy * cell + grout_px // 2
            c = rnd.choice(palette)
            draw.rectangle([x0, y0, x0 + cell - grout_px, y0 + cell - grout_px], fill=c)
    return img


def _encaustic(w, h, grid=5):
    """Patterned cement tile — single tile image with a symmetric motif."""
    img = _base_img(w, h, (216, 211, 201))
    draw = ImageDraw.Draw(img)
    base = (216, 211, 201)
    cx, cy = w // 2, h // 2
    bw = max(8, w // 40)
    draw.rectangle([bw, bw, w - bw, h - bw], outline=(58, 68, 108), width=bw)
    r = w // 6
    for sx, sy in [(bw * 2, bw * 2), (w - bw * 2, bw * 2), (bw * 2, h - bw * 2), (w - bw * 2, h - bw * 2)]:
        draw.arc([sx - r, sy - r, sx + r, sy + r], 0, 90, fill=(58, 68, 108), width=bw)
        draw.arc([sx - r, sy - r, sx + r, sy + r], 180, 270, fill=(58, 68, 108), width=bw)
    draw.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], fill=(58, 68, 108))
    draw.ellipse([cx - r // 6, cy - r // 6, cx + r // 6, cy + r // 6], fill=base)
    return img


def _hex(w, h):
    img = _base_img(w, h)
    draw = ImageDraw.Draw(img)
    grout = (192, 192, 192)
    draw.rectangle([0, 0, w - 1, h - 1], fill=grout)
    rnd = random.Random(9)
    r = max(24, w // 8)
    hh = int(r * 0.866)
    y = 0
    row = 0
    while y < h + hh:
        x = 0 if row % 2 == 0 else -r // 2
        while x < w + r:
            c = rnd.choice([(250, 250, 250), (244, 244, 244), (252, 252, 252), (238, 238, 238)])
            draw.polygon(
                [(x, y), (x + r // 2, y - hh), (x + r, y), (x + r, y + hh), (x + r // 2, y + 2 * hh), (x, y + hh)],
                fill=c,
            )
            x += r + 2
        y += hh * 2
        row += 1
    return img


def _specs():
    S = []
    # Each spec: pattern renders full-bleed; grout is drawn after.
    # ---- wall tiles ----
    S.append(dict(slug="subway-white-600x300", name="White Subway Tile", category="wall-tiles", w=600, h=300,
                  colour="white", finish="gloss", material="ceramic", pattern="plain",
                  base=(250, 250, 250), grout_px=8))
    S.append(dict(slug="subway-grey-600x300", name="Grey Subway Tile", category="wall-tiles", w=600, h=300,
                  colour="grey", finish="matte", material="ceramic", pattern="plain",
                  base=(186, 189, 193), grout_px=8))
    S.append(dict(slug="metro-black-600x300", name="Black Metro Tile", category="wall-tiles", w=600, h=300,
                  colour="black", finish="gloss", material="ceramic", pattern="plain",
                  base=(30, 30, 32), grout_px=8))
    S.append(dict(slug="marble-white-600x300", name="Carrara White Marble", category="wall-tiles", w=600, h=300,
                  colour="white", finish="gloss", material="ceramic", pattern="marble",
                  base=(244, 244, 246), grout_px=8, marble=True))
    S.append(dict(slug="marble-charcoal-600x300", name="Charcoal Marble", category="wall-tiles", w=600, h=300,
                  colour="grey", finish="gloss", material="ceramic", pattern="marble",
                  base=(58, 60, 64), grout_px=8, marble=True, tone=(120, 124, 132), veins=12))
    S.append(dict(slug="ceramic-mint-600x300", name="Mint Ceramic Tile", category="wall-tiles", w=600, h=300,
                  colour="green", finish="gloss", material="ceramic", pattern="plain",
                  base=(178, 207, 198), grout_px=8))
    S.append(dict(slug="ceramic-sage-600x300", name="Sage Green Tile", category="wall-tiles", w=600, h=300,
                  colour="green", finish="matte", material="ceramic", pattern="plain",
                  base=(179, 191, 161), grout_px=8))
    S.append(dict(slug="ceramic-navy-600x300", name="Navy Blue Tile", category="wall-tiles", w=600, h=300,
                  colour="blue", finish="gloss", material="ceramic", pattern="plain",
                  base=(44, 59, 95), grout_px=8))
    S.append(dict(slug="stone-beige-600x300", name="Beige Stone Tile", category="wall-tiles", w=600, h=300,
                  colour="beige", finish="matte", material="natural stone", pattern="stone",
                  base=(217, 206, 187), grout_px=8))
    S.append(dict(slug="mosaic-white-200x200", name="White Mosaic", category="wall-tiles", w=200, h=200,
                  colour="white", finish="gloss", material="ceramic", pattern="mosaic", mosaic=True))
    S.append(dict(slug="hex-white-200x200", name="Hex White Mosaic", category="wall-tiles", w=200, h=200,
                  colour="white", finish="gloss", material="ceramic", pattern="mosaic", hex=True))
    # ---- floor tiles ----
    S.append(dict(slug="porcelain-light-grey-600x600", name="Light Grey Porcelain", category="floor-tiles", w=600, h=600,
                  colour="grey", finish="matte", material="porcelain", pattern="plain",
                  base=(201, 203, 206), grout_px=6))
    S.append(dict(slug="porcelain-anthracite-600x600", name="Anthracite Porcelain", category="floor-tiles", w=600, h=600,
                  colour="grey", finish="matte", material="porcelain", pattern="plain",
                  base=(66, 68, 72), grout_px=6))
    S.append(dict(slug="stone-slate-600x600", name="Slate Effect Tile", category="floor-tiles", w=600, h=600,
                  colour="grey", finish="matte", material="porcelain", pattern="stone",
                  base=(148, 150, 152), grout_px=8, stone=True))
    S.append(dict(slug="terrazzo-light-600x600", name="Light Terrazzo", category="floor-tiles", w=600, h=600,
                  colour="beige", finish="matte", material="porcelain", pattern="terrazzo",
                  base=(235, 230, 220), grout_px=6, terrazzo=True))
    S.append(dict(slug="encaustic-blue-200x200", name="Blue Encaustic Cement", category="floor-tiles", w=200, h=200,
                  colour="blue", finish="matte", material="cement", pattern="encaustic", encaustic=True))
    S.append(dict(slug="wood-oak-plank-1200x200", name="Oak Wood Effect Plank", category="floor-tiles", w=1200, h=200,
                  colour="wood", finish="matte", material="porcelain", pattern="wood",
                  base=(197, 161, 111), grout_px=5, wood=True))
    S.append(dict(slug="wood-walnut-plank-1200x200", name="Walnut Wood Effect Plank", category="floor-tiles", w=1200, h=200,
                  colour="wood", finish="matte", material="porcelain", pattern="wood",
                  base=(129, 89, 55), grout_px=5, wood=True))
    # ---- panels ----
    S.append(dict(slug="panel-tile-effect-white-1200x2400", name="White Tile Effect Panel", category="panels", w=1200, h=2400,
                  colour="white", finish="gloss", material="multiboard", pattern="tile-effect",
                  base=(250, 250, 250), grout_px=10, panel=True))
    S.append(dict(slug="panel-wood-effect-1200x2400", name="Oak Effect Panel", category="panels", w=1200, h=2400,
                  colour="wood", finish="matte", material="multiboard", pattern="wood-effect",
                  base=(197, 161, 111), wood=True, panel=True))
    # ---- ceiling ----
    S.append(dict(slug="ceiling-white-pvc-600x600", name="White PVC Ceiling", category="ceiling", w=600, h=600,
                  colour="white", finish="matte", material="pvc", pattern="plain",
                  base=(248, 248, 246), grout_px=6))
    return S


def render_all():
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in _specs():
        slug = spec["slug"]
        cat = spec["category"]
        dirp = OUT / cat / slug
        dirp.mkdir(parents=True, exist_ok=True)
        ar = spec["w"] / spec["h"]
        if ar >= 1:
            W, H = 1024, max(256, int(1024 / ar))
        else:
            H, W = 1024, max(256, int(1024 * ar))

        # full-bleed pattern first
        img = _base_img(W, H, spec.get("base", (240, 240, 240)))
        if spec.get("marble"):
            img = _marble(img, tone=spec.get("tone", (110, 116, 130)), veins=spec.get("veins", 16))
        elif spec.get("wood"):
            img = _wood_grain(img, planks=8 if spec.get("panel") else 5)
        elif spec.get("terrazzo"):
            img = _terrazzo(img)
        elif spec.get("stone"):
            img = _stone_texture(img)
        elif spec.get("encaustic"):
            img = _encaustic(W, H)
        elif spec.get("mosaic"):
            img = _mosaic(W, H)
        elif spec.get("hex"):
            img = _hex(W, H)

        # grout over pattern (seamless: one strip at left/top; the adjacent
        # repeat's strip closes the right/bottom edge)
        if not spec.get("mosaic") and not spec.get("hex") and not spec.get("encaustic"):
            gw = spec.get("grout_px", 6)
            img = _draw_grout(img, max(1, W - gw), max(1, H - gw), gw, (186, 186, 186))

        img = _noise(img, amount=4, seed=hash(slug) % 997)
        img = img.filter(ImageFilter.GaussianBlur(0.4))
        albedo = dirp / "albedo.jpg"
        img.save(albedo, quality=88)

        grey = img.convert("L")
        emb = ImageOps.autocontrast(grey.filter(ImageFilter.EMBOSS)).convert("RGB")
        emb.save(dirp / "normal.jpg", quality=88)

        prev = img.copy()
        prev.thumbnail((256, 256))
        prev.save(dirp / "preview.jpg", quality=80)

        MANIFEST.append(
            {
                "slug": slug,
                "name": spec["name"],
                "category": cat,
                "tile_width_mm": spec["w"],
                "tile_height_mm": spec["h"],
                "thickness_mm": 9,
                "colour_family": spec["colour"],
                "finish": spec["finish"],
                "material": spec["material"],
                "pattern": spec["pattern"],
                "source_type": "custom",
                "license": "custom",
                "maps": {
                    "albedo": f"/textures/{cat}/{slug}/albedo.jpg",
                    "normal": f"/textures/{cat}/{slug}/normal.jpg",
                    "preview": f"/textures/{cat}/{slug}/preview.jpg",
                },
            }
        )
        print(f"  ✓ {slug} ({W}x{H})")
    (OUT / "manifest.json").write_text(json.dumps({"textures": MANIFEST}, indent=2))
    print(f"Done: {len(MANIFEST)} textures → {OUT}")


if __name__ == "__main__":
    render_all()

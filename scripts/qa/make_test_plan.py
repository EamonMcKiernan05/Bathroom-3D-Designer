"""Draw a realistic hand-drawn bathroom plan image (for QA / testing photo->plan import).

Writes scripts/qa/test-plan.png — a pencil-style annotated room sketch with dimensions,
door, window and a shower, so a vision model has something real to read.
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "test-plan.png"


def hand(font, size, shades_of_grey=True):
    pass


def draw():
    W, H = 1200, 900
    img = Image.new("RGB", (W, H), (252, 250, 246))  # notepad paper
    d = ImageDraw.Draw(img)
    rnd = random.Random(7)

    # faint ruled lines (notebook)
    for y in range(0, H, 28):
        d.line([(0, y), (W, y)], fill=(238, 235, 228), width=1)

    def jitter(points, amp=4):
        return [(x + rnd.randint(-amp, amp), y + rnd.randint(-amp, amp)) for x, y in points]

    # room outline (rectangle 2400 x 1800mm) with slight hand wobble
    m = 120  # margin
    box = [(m, m), (W - m, m), (W - m, H - m), (m, H - m)]
    poly = jitter(box, amp=3)
    d.line(poly + [poly[0]], fill=(60, 60, 70), width=3)

    # dimension arrows + labels
    ink = (70, 66, 80)
    try:
        f = ImageFont.truetype("arial.ttf", 26)
        fs = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        f = fs = ImageFont.load_default()

    def dim(v, x1, y1, x2, y2, text, off_x=0, off_y=0, label_off=0):
        d.line([(x1, y1), (x1 + 12, y1)], fill=ink, width=2)
        d.line([(x2, y2), (x2 - 12, y2)], fill=ink, width=2)
        d.line([(x1 + 4, y1), (x2 - 4, y2)], fill=ink, width=2)
        d.text((x1 + off_x + label_off, y1 + off_y), text, fill=ink, font=f)

    # top: 2400
    dim(2400, m + 20, m - 30, W - m - 20, m - 30, "2400", off_x=-40, off_y=-30, label_off=-20)
    # left: 1800
    dim(1800, m - 40, m + 25, m - 40, H - m - 25, "1800", off_x=-60, off_y=-10, label_off=-30)

    # door on bottom wall (open arc)
    door = (int(W * 0.62), H - m)
    dw = 70
    d.line([(door[0] - dw, door[1]), (door[0] + dw, door[1])], fill=(150, 90, 60), width=4)
    d.arc([door[0] - dw, door[1] - dw, door[0] + dw, door[1] + dw], 0, 90, fill=(150, 90, 60), width=3)
    d.text((door[0] - 30, door[1] + 8), "900", fill=ink, font=fs)

    # window on top wall
    wx1, wx2 = int(W * 0.30), int(W * 0.55)
    wy = m + 4
    d.line([(wx1, wy), (wx2, wy)], fill=(70, 120, 170), width=5)
    for x in range(wx1, wx2, 18):
        d.line([(x, wy - 6), (x, wy + 6)], fill=(70, 120, 170), width=2)
    d.text((wx1, wy - 26), "1200", fill=ink, font=fs)

    # shower in top-right corner
    sx, sy = int(W * 0.82), int(H * 0.25)
    r = 70
    d.arc([sx - r, sy - r, sx + r, sy + r], 0, 90, fill=(90, 110, 130), width=3)
    d.line([(sx, sy), (sx, sy - r)], fill=(90, 110, 130), width=3)
    d.line([(sx, sy), (sx + r, sy)], fill=(90, 110, 130), width=3)
    pts = [(sx + 6, sy - 8), (sx + 12, sy - 16), (sx + 18, sy - 8), (sx + 24, sy - 18), (sx + 30, sy - 6)]
    d.line(pts, fill=(60, 60, 70), width=2)
    d.text((sx - 50, sy + r), "900", fill=ink, font=fs)

    # toilet + basin on left
    # basin
    bx, by = int(W * 0.18), int(H * 0.35)
    d.ellipse([bx - 34, by - 24, bx + 34, by + 24], outline=(95, 95, 105), width=3)
    d.line([(bx - 30, by + 40), (bx + 30, by + 40)], fill=(95, 95, 105), width=3)
    d.text((bx - 34, by + 46), "450", fill=ink, font=fs)
    # toilet
    tx, ty = int(W * 0.16), int(H * 0.68)
    d.ellipse([tx - 34, ty - 22, tx + 34, ty + 22], outline=(95, 95, 105), width=3)
    d.polygon([(tx - 20, ty - 22), (tx + 20, ty - 22), (tx + 24, ty - 60), (tx - 24, ty - 60)], outline=(95, 95, 105), width=3)
    d.text((tx - 44, ty + 26), "700", fill=ink, font=fs)

    # ceiling height annotation
    d.text((m, H - 70), "ceiling 2400", fill=(140, 110, 60), font=f)

    # sketchy border double line
    d.rectangle([m - 14, m - 14, W - m + 14, H - m + 14], outline=(200, 196, 188), width=2)

    img.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    draw()

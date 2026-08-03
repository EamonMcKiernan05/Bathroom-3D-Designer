"""Generate a CLEAR, high-contrast dimensioned bathroom plan (for OCR testing).

Unlike the hand-jittered sketch, this uses big bold dimension labels and thick
strokes so an OCR model can actually read the numbers — closer to a real
architect's plan. 1600x1200.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "clear-plan.png"


def draw(width=2400, depth=1800, out="clear-plan.png"):
    W, H = 1600, 1200
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        big = ImageFont.truetype("arialbd.ttf", 72)
        big2 = ImageFont.truetype("arialbd.ttf", 60)
        med = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        big = big2 = med = ImageFont.load_default()

    ink = (20, 20, 30)
    m = 180
    box = [(m, m), (W - m, m), (W - m, H - m), (m, H - m)]
    d.line(box + [box[0]], fill=ink, width=8)

    # wall thickness double-line (suggest a real wall)
    d.line([(m + 40, m + 40), (W - m - 40, m + 40)], fill=ink, width=4)
    d.line([(m + 40, H - m - 40), (W - m - 40, H - m - 40)], fill=ink, width=4)

    # dimension labels (big, centered on each edge, ABOVE/BESIDE the outline)
    d.text(((W) // 2 - 60, m - 100), str(width), fill=ink, font=big)          # top: width
    d.text((m - 150, (H) // 2 - 40), str(depth), fill=ink, font=big, anchor="mm")  # left: depth
    d.text((W // 2 - 60, H - m + 20), str(width), fill=ink, font=big)         # bottom
    d.text((W - m + 20, H // 2 - 40), str(depth), fill=ink, font=big)         # right

    # door opening on bottom wall with 900 label
    door_cx = int(W * 0.62)
    d.line([(door_cx - 140, H - m), (door_cx + 140, H - m)], fill=(30, 30, 30), width=8)
    d.arc([door_cx - 140, H - m - 140, door_cx + 140, H - m + 140], 0, 90, fill=(30, 30, 30), width=6)
    d.text((door_cx + 10, H - m + 30), "900", fill=(30, 30, 30), font=big2)
    d.text((door_cx - 160, H - m + 30), "door", fill=(90, 90, 110), font=med)

    # window on top wall with 1200 label
    wx1, wx2 = int(W * 0.30), int(W * 0.55)
    d.line([(wx1, m), (wx2, m)], fill=(30, 80, 160), width=10)
    for x in range(wx1, wx2, 40):
        d.line([(x, m - 20), (x, m + 20)], fill=(30, 80, 160), width=4)
    d.text((int((wx1 + wx2) / 2) - 30, m - 55), "1200", fill=(30, 80, 160), font=big2)

    # ceiling annotation
    d.text((m + 20, H - 80), "ceiling 2400", fill=(120, 90, 40), font=big2)

    img.save(Path(__file__).resolve().parent / out)
    print(f"Wrote {Path(__file__).resolve().parent / out}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        draw(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "clear-plan.png")
    else:
        draw()

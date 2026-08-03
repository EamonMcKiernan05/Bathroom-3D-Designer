"""Photo → floor-plan conversion via a local Vision LLM (e.g. Gemma 4 E2B/E4B edge models).

The endpoint accepts an uploaded photo of a hand-drawn bathroom plan / measurement
sketch, sends it to an OpenAI-compatible vision endpoint (llama.cpp / vLLM / Ollama),
asks it to return strict JSON matching our room schema, normalizes that JSON into a
safe, clockwise room plan, and returns it for the frontend to load into the editor.

Configure with environment variables:
  PLAN_VISION_BASE_URL  e.g. http://127.0.0.1:8080/v1   (llama-server with --mmproj)
  PLAN_VISION_MODEL     e.g. gemma-4-E2B-it  or  gemma-4-12b-it
  PLAN_VISION_API_KEY   optional

Serve Gemma 4 vision with llama.cpp:
  llama-server -m <text>.gguf --mmproj <mmproj>.gguf -c 8192
"""
import base64
import io
import json
import os
import re
import subprocess
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from PIL import Image

router = APIRouter(prefix="/api/v1/plans", tags=["plans"])

# Repo root = apps/api/app/<file> -> 4 up
_REPO = Path(__file__).resolve().parent.parent.parent.parent
_PS1 = _REPO / "scripts" / "ocr" / "serve.ps1"
_SH = _REPO / "scripts" / "ocr" / "serve.sh"

# Default to a SELF-HOSTED OCR model (llama-server with --mmproj, e.g. Unlimited-OCR).
# No external API: point these at your own llama.cpp vision server (scripts/serve-ocr.sh).
BASE_URL = os.environ.get("PLAN_VISION_BASE_URL", "http://127.0.0.1:9333/v1")
MODEL = os.environ.get("PLAN_VISION_MODEL", "")
API_KEY = os.environ.get("PLAN_VISION_API_KEY", "")

PROMPT = "<|grounding|>OCR this image."

# DeepSeek-OCR / Unlimited-OCR response format (per sahilchachra card):
#   <|det|>text [x1,y1,x2,y2]<|/det|>content   (mtmd-cli)   OR   plain lines
#   image [x1,y1,x2,y2]                         (whole-image placeholder)
#   text [x1,y1,x2,y2]content                   (llama-server OpenAI form)
# Coordinates are in the model's normalised input space (0..999 each axis).


def _extract_json(text: str) -> dict:
    text = text.strip()
    # strip code fences / leading prose
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in model output")
    return json.loads(m.group(0))


_REGION = re.compile(
    r"^(image|text|header)\s*\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]\s*(.*)$",
    re.IGNORECASE,
)


def _parse_regions(ocr_text: str) -> list[dict]:
    """Parse Unlimited-OCR output into a list of {type,x1,y1,x2,y2,content}."""
    text = ocr_text.replace("<|det|>", "").replace("<|/det|>", "")
    regions = []
    for line in text.splitlines():
        m = _REGION.match(line.strip())
        if not m:
            continue
        regions.append(
            {
                "type": m.group(1).lower(),
                "x1": int(m.group(2)), "y1": int(m.group(3)),
                "x2": int(m.group(4)), "y2": int(m.group(5)),
                "content": m.group(6).strip(),
            }
        )
    return regions


def _reconstruct_room(ocr_text: str) -> dict:
    """Turn Unlimited-OCR region output into a room plan.

    Heuristic but reasonable: read dimension labels + their edge positions, infer a
    rectangular (or axis-aligned) room, and place any door/window labels on the
    wall they sit nearest. Works best on clearly-measured plans (which is what a
    user photographs). Position/type can be refined in the editor afterwards.
    """
    regions = _parse_regions(ocr_text)
    labels = []
    for r in regions:
        if r["type"] != "text":
            continue
        c = r["content"]
        if not c or c in ("[EMPTY]", "--"):
            continue
        nums = re.findall(r"\d{2,5}", c)
        if not nums:
            continue
        n = int(nums[-1])
        labels.append(
            {
                "n": n,
                "cx": (r["x1"] + r["x2"]) / 2.0,
                "cy": (r["y1"] + r["y2"]) / 2.0,
                "edge": _edge_of(r, 1000, 1000),
                "tag": c.lower().replace(" ", ""),
            }
        )
    if not labels:
        raise ValueError("OCR found no readable dimensions in the plan image")

    # ceiling height: from a "ceiling" tag, else largest value in a sensible range
    ceiling = next((L["n"] for L in labels if "ceiling" in L["tag"]), None)
    if not ceiling:
        ceiling = max([L["n"] for L in labels if 2000 <= L["n"] <= 5000], default=2400)

    # overall width (horizontal dimension) & depth (vertical dimension)
    def wall_of(L):
        # image edges -> room walls: top/bottom -> horizontal (width), left/right -> vertical (depth)
        return "width" if L["edge"] in ("top", "bottom") else "depth"

    h = [L for L in labels if wall_of(L) == "width"]
    v = [L for L in labels if wall_of(L) == "depth"]
    width = max(h, key=lambda L: L["n"])["n"] if h else None
    depth = max(v, key=lambda L: L["n"])["n"] if v else None
    if not width or not depth:
        # fallback: assign largest remaining numeric as the missing side
        for L in sorted(labels, key=lambda x: x["n"], reverse=True):
            if L["n"] >= 1500:
                if width is None and wall_of(L) == "width":
                    width = L["n"]
                elif depth is None and wall_of(L) == "depth":
                    depth = L["n"]
    width = _clamp(width or 2400, 600, 20000)
    depth = _clamp(depth or 1800, 600, 20000)
    ceiling = int(_clamp(ceiling or 2400, 1500, 5000))

    # floor: axis-aligned rectangle centred on origin (matches editor expectations)
    w, d = width, depth
    floor = [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]]

    # wall index for each image edge (clockwise, matching buildWalls)
    edge_wall = {"top": 2, "bottom": 0, "left": 3, "right": 1}

    doors, windows = [], []
    used_nums = {width, depth}
    # flag dimension-label ids so we don't turn the main dims into openings
    dim_ids = set()
    for i, L in enumerate(labels):
        if L["n"] == width or L["n"] == depth:
            dim_ids.add(i)

    for i, L in enumerate(labels):
        if i in dim_ids:
            continue
        if L["n"] < 200 or L["n"] > 2400:
            continue  # too small to be an opening, too big to be a wall
        wall = edge_wall.get(L["edge"], 0)
        # proportional position along that wall (0..1), mirroring image axis
        frac_x = L["cx"] / 1000.0
        frac_y = L["cy"] / 1000.0
        # convert to mm from each wall's start (clockwise)
        pos = {
            0: w * frac_x,          # bottom wall, left->right
            1: d * frac_y,          # right wall, top->bottom (image y down = +z)
            2: w * (1 - frac_x),    # top wall, right->left
            3: d * (1 - frac_y),    # left wall, bottom->top
        }[wall]
        pos = max(50, min(pos, (w if wall in (0, 2) else d) - 50))
        if "window" in L["tag"] or 1300 <= L["n"] <= 1900:
            windows.append({"wall": wall, "pos": pos, "width": L["n"] if L["n"] < 2000 else 1100, "height": 1200, "sill": 900})
        else:
            doors.append({"wall": wall, "pos": pos, "width": L["n"] if 600 <= L["n"] <= 1300 else 850, "height": 2100})

    walls = [{"profile": "rectangle", "height": ceiling} for _ in range(4)]
    return {
        "floor": floor,
        "ceilingHeight": ceiling,
        "wallThickness": 100,
        "walls": walls,
        "doors": doors,
        "windows": windows,
    }


def _edge_of(r, w, h):
    """Which image edge is region r nearest to."""
    d = {
        "top": r["y1"],
        "bottom": h - r["y2"],
        "left": r["x1"],
        "right": w - r["x2"],
    }
    return min(d, key=d.get)


def _clamp(v, lo, hi, default=None):
    try:
        f = float(v)
        return max(lo, min(hi, f))
    except (TypeError, ValueError):
        return default


def _normalize_plan(raw: dict) -> dict:
    floor_raw = raw.get("floor") or raw.get("floor_points") or raw.get("outline") or []
    pts: list[list[float]] = []
    for p in floor_raw:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            x = float(p[0])
            z = float(p[1])
            if pts and abs(pts[-1][0] - x) < 5 and abs(pts[-1][1] - z) < 5:
                continue
            pts.append([round(x, 1), round(z, 1)])
    if len(pts) < 3:
        raise ValueError("Model did not return a usable floor outline")

    # clockwise order (negative shoelace area in XZ)
    area = 0.0
    for i in range(len(pts)):
        x1, z1 = pts[i]
        x2, z2 = pts[(i + 1) % len(pts)]
        area += (x2 - x1) * (z2 + z1)
    if area < 0:  # make clockwise
        pts = list(reversed(pts))

    ceiling = _clamp(raw.get("ceiling_height") or raw.get("ceilingHeight") or 2400, 1500, 5000, 2400)
    walls_raw = raw.get("walls") or raw.get("wall_shapes") or []
    walls = []
    for i in range(len(pts)):
        w = walls_raw[i] if i < len(walls_raw) and isinstance(walls_raw[i], dict) else {}
        profile = w.get("profile", "rectangle")
        if profile not in ("rectangle", "gable", "stairs", "boxing"):
            profile = "rectangle"
        walls.append({
            "profile": profile,
            "height": _clamp(w.get("height", ceiling), 400, 5000, ceiling),
            "slopeRise": _clamp(w.get("slopeRise", 0), 0, 2000, 0),
            "stairSteps": int(_clamp(w.get("stairSteps", 6), 2, 15, 6)),
            "boxLength": _clamp(w.get("boxLength", 0), 0, 20000, 0),
            "boxDepth": _clamp(w.get("boxDepth", 120), 20, 800, 120),
            "boxFrom": _clamp(w.get("boxFrom", 0), 0, 20000, 0),
            "boxTop": _clamp(w.get("boxTop", 450), 100, ceiling - 100, 450),
        })

    doors = []
    for d in (raw.get("doors") or []):
        if isinstance(d, dict):
            doors.append({
                "wall": int(_clamp(d.get("wall", 0), 0, len(walls) - 1, 0)),
                "pos": _clamp(d.get("pos", 0), 0, 20000, 0),
                "width": _clamp(d.get("width", 850), 600, 1500, 850),
                "height": _clamp(d.get("height", 2100), 1800, 2400, 2100),
            })
    windows = []
    for d in (raw.get("windows") or []):
        if isinstance(d, dict):
            windows.append({
                "wall": int(_clamp(d.get("wall", 0), 0, len(walls) - 1, 0)),
                "pos": _clamp(d.get("pos", 0), 0, 20000, 0),
                "width": _clamp(d.get("width", 1100), 500, 2500, 1100),
                "height": _clamp(d.get("height", 1200), 400, 2500, 1200),
                "sill": _clamp(d.get("sill", 900) or d.get("sillheight", 900), 200, 2000, 900),
            })

    return {
        "floor": pts,
        "ceilingHeight": ceiling,
        "wallThickness": _clamp(raw.get("wallThickness", 100), 40, 300, 100),
        "walls": walls,
        "doors": doors,
        "windows": windows,
    }


def _call_vision(image_b64: str, media_type: str) -> str:
    if not BASE_URL:
        raise HTTPException(503, "Vision model not configured. Set PLAN_VISION_BASE_URL.")
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    payload: dict = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                ],
            }
        ],
        # temp 0 is required for deterministic OCR; repeat-penalty stops the
        # model looping on dense/partial text.
        "temperature": 0,
        "repeat_penalty": 1.05,
        "max_tokens": 3000,
    }
    if MODEL:
        payload["model"] = MODEL
    try:
        resp = httpx.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Local OCR server unavailable or failed: {e}")


def _engine_online() -> bool:
    """Is the local OCR llama-server reachable?"""
    if not BASE_URL:
        return False
    try:
        return httpx.get(f"{BASE_URL}/models", timeout=2).status_code == 200
    except Exception:
        return False


def _runtime_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local"))) if os.name == "nt" else Path.home() / ".local/share"
    return base / ("bathroom-3d-ocr" if os.name == "nt" else "bathroom-ocr")


def _runtime_detail() -> dict:
    rt = _runtime_dir()
    bin_ = next((rt / "llama").rglob("llama-server.exe"), None) if os.name == "nt" else next((rt / "llama").rglob("llama-server"), None)
    # accept either default engine model (Gemma) or the Unlimited-OCR alternative
    candidates = [
        rt / "models" / "gemma-4-E4B-it-Q4_K_M.gguf",
        rt / "models" / "Unlimited-OCR-Q4_K_M.gguf",
    ]
    model_present = any(p.exists() for p in candidates)
    mmproj_candidates = [
        rt / "models" / "mmproj-gemma-4-E4B-F16.gguf",
        rt / "models" / "mmproj-Unlimited-OCR-F16.gguf",
    ]
    mmproj_present = any(p.exists() for p in mmproj_candidates)
    return {
        "runtime_dir": str(rt),
        "binary_present": bin_ is not None,
        "llama_model_present": model_present,
        "mmproj_present": mmproj_present,
        "engine_running": _engine_online(),
    }


def _start_engine(max_wait: int = 100) -> dict:
    """Provision (download if needed) and launch the OCR engine. Idempotent."""
    if _engine_online():
        return {"started": False, "ok": True, "message": "Engine already running"}
    if not (_PS1.exists() or _SH.exists()):
        return {"started": False, "ok": False, "message": "OCR installer script not found"}
    try:
        if os.name == "nt":
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(_PS1)]
            creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
        else:
            subprocess.Popen(["bash", str(_SH)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return {"started": False, "ok": False, "message": f"Failed to launch engine: {e}"}
    for _ in range(max_wait):
        if _engine_online():
            return {"started": True, "ok": True, "message": "Engine started"}
        time.sleep(1)
    return {"started": True, "ok": False, "message": "Engine launch attempted but not yet online (first run downloads ~2.6GB)"}


@router.get("/status")
async def plan_status():
    detail = _runtime_detail()
    return {
        "configured": bool(BASE_URL),
        "base_url": BASE_URL,
        "model": MODEL or "default",
        "online": _engine_online(),
        **detail,
    }


@router.post("/engine/start")
async def plan_engine_start():
    return _start_engine()


@router.post("/from-photo")
async def plan_from_photo(file: UploadFile):
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")
    # downscale >1600px and re-encode to keep the sketch legible but the payload small
    try:
        img = Image.open(io.BytesIO(raw))
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        image_b64 = base64.b64encode(buf.getvalue()).decode()
        media_type = "image/jpeg"
    except Exception:
        image_b64 = base64.b64encode(raw).decode()
        media_type = file.content_type or "image/jpeg"

    try:
        # Seamless: if the local OCR engine isn't up, boot it first (first run
        # downloads the model, so this may take a while).
        if not _engine_online():
            _start_engine(max_wait=15)
        raw_text = _call_vision(image_b64, media_type)
        # Two engines:
        #  - a general VLM (e.g. Gemma) returns JSON we normalise directly
        #  - the OCR specialist (Unlimited-OCR) returns <region> OCR text we reconstruct
        try:
            return _normalize_plan(_extract_json(raw_text))
        except (ValueError, json.JSONDecodeError):
            return _reconstruct_room(raw_text)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, f"Could not parse the plan from the photo: {e}")

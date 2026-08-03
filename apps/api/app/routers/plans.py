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

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from PIL import Image

router = APIRouter(prefix="/api/v1/plans", tags=["plans"])

BASE_URL = os.environ.get("PLAN_VISION_BASE_URL", "").rstrip("/")
MODEL = os.environ.get("PLAN_VISION_MODEL", "")
API_KEY = os.environ.get("PLAN_VISION_API_KEY", "")

PROMPT = """You are a bathroom-plan reader. Below is a photo of a hand-drawn bathroom floor plan and/or measurement sketch.
Read the sketch and any handwritten dimensions, then output ONLY valid JSON (no commentary, no markdown) matching EXACTLY this schema:
{
  "floor": [[x, z], [x, z], ...],        // room outline corners in MILLIMETRES, clockwise, minimum 3 points, centred near the origin (e.g. [-1200,-900]..[1200,900] for a 2400x1800 room)
  "ceiling_height": 2400,                // mm
  "walls": [                             // one per floor edge, in the same order
    { "profile": "rectangle", "height": 2400, "slopeRise": 0, "stairSteps": 6, "boxLength": 0, "boxDepth": 120, "boxFrom": 0, "boxTop": 450 }
  ],
  "doors":  [{ "wall": 0, "pos": 900, "width": 850, "height": 2100 }],
  "windows":[{ "wall": 1, "pos": 1200, "width": 1100, "height": 1200, "sill": 900 }]
}
Only include walls/doors/windows you can actually infer. If no dimensions are readable, estimate sensible UK bathroom sizes. Use the single wall profile "rectangle" unless a roof/stairs/boxing is clearly indicated (then "gable", "stairs", or "boxing")."""


def _extract_json(text: str) -> dict:
    text = text.strip()
    # strip code fences / leading prose
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in model output")
    return json.loads(m.group(0))


def _clamp(v, lo, hi, default):
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


def _call_vision(image_b64: str, media_type: str) -> dict:
    if not BASE_URL or not MODEL:
        raise HTTPException(
            503,
            "Vision model not configured. Set PLAN_VISION_BASE_URL (OpenAI-compatible vision "
            "endpoint, e.g. a llama.cpp server with --mmproj) and PLAN_VISION_MODEL.",
        )
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Read this hand-drawn plan and output the JSON."},
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
    }
    try:
        resp = httpx.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return _extract_json(data["choices"][0]["message"]["content"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Vision model call failed: {e}")


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
        raw_plan = _call_vision(image_b64, media_type)
        return _normalize_plan(raw_plan)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, f"Could not parse the plan from the photo: {e}")

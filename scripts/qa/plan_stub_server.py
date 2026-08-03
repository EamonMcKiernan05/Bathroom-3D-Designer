"""OpenAI-compatible VISION STUB for QA-testing /api/v1/plans/from-photo.

Serves POST /v1/chat/completions on 127.0.0.1:9333 and returns a realistic
room-plan JSON (as a vision model would). It ignores the image content and returns
a fixed plan unless an override file exists at scripts/qa/plan_override.json
(which must contain the raw `floor`/`doors`/`windows` JSON).

This lets us test the full photo->plan pipeline (endpoint -> normalize -> frontend -> draw)
deterministically, WITHOUT a real vision model. For real inference, run scripts/serve-ocr.sh
and stop this stub.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

OVERRIDE = Path(__file__).resolve().parent / "plan_override.json"

DEFAULT_PLAN = {
    "floor": [[-1200, -900], [1200, -900], [1200, 900], [-1200, 900]],
    "ceilingHeight": 2400,
    "wallThickness": 100,
    "walls": [
        {"profile": "rectangle", "height": 2400},
        {"profile": "rectangle", "height": 2400},
        {"profile": "rectangle", "height": 2400},
        {"profile": "rectangle", "height": 2400},
    ],
    "doors": [{"wall": 2, "pos": 900, "width": 850, "height": 2100}],
    "windows": [{"wall": 0, "pos": 1200, "width": 1100, "height": 1200, "sill": 900}],
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()

    def do_POST(self):
        if self.path.split("?")[0] != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        plan = DEFAULT_PLAN
        if OVERRIDE.exists():
            try:
                plan = json.loads(OVERRIDE.read_text())
            except Exception:
                pass
        content = json.dumps(plan)
        resp = {
            "id": "chatcmpl-qa-stub",
            "object": "chat.completion",
            "created": 0,
            "model": "qa-stub-vision",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    port = int(os.environ.get("QA_STUB_PORT", "9333"))
    print(f"[plan-stub] serving OpenAI-compatible vision on 127.0.0.1:{port}  (override: {OVERRIDE})")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()

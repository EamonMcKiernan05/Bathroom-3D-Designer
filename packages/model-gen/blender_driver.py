"""Drive Blender via the MCP addon socket (127.0.0.1:9876) to build parametric models.

Usage:
  python blender_driver.py toilet          # build one model
  python blender_driver.py --all           # build every model in BUILDERS
  python blender_driver.py --list          # list builders
"""
import json
import socket
import sys
from pathlib import Path

HOST, PORT = "127.0.0.1", 9876
LIB = Path(__file__).parent / "blender_lib.py"


def send_command(cmd_type, params, timeout=120):
    s = socket.create_connection((HOST, PORT), timeout=10)
    s.sendall(json.dumps({"type": cmd_type, "params": params}).encode())
    s.settimeout(timeout)
    data = b""
    try:
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
            if len(data) > 4_000_000:
                break
    except socket.timeout:
        pass
    s.close()
    return json.loads(data.decode("utf-8", "replace"))


def build(slug: str) -> dict:
    code = f"BUILD = '{slug}'\n" + LIB.read_text(encoding="utf-8")
    resp = send_command("execute_code", {"code": code})
    if resp.get("status") != "success":
        return {"ok": False, "slug": slug, "error": resp.get("message", str(resp)[:500])}
    inner = resp.get("result", {})
    stdout = inner.get("result", "") if isinstance(inner, dict) else str(inner)
    ok = "BUILD_OK" in stdout and "EXPORTED" in stdout
    return {"ok": ok, "slug": slug, "stdout": stdout[-1200:]}


def main():
    args = sys.argv[1:]
    if not args or "--list" in args:
        print("Builders: toilet basin bath shower-tray shower-screen radiator towel-rail "
              "mirror cabinet vanity-unit tap shower-head shower-set shelf towel-ring robe-hook soap-dish")
        return
    if "--all" in args:
        slugs = ["toilet", "basin", "bath", "shower-tray", "shower-screen", "radiator",
                 "towel-rail", "mirror", "cabinet", "vanity-unit", "tap", "shower-head",
                 "shower-set", "shelf", "towel-ring", "robe-hook", "soap-dish"]
        results = [build(s) for s in slugs]
        ok_count = sum(1 for r in results if r["ok"])
        for r in results:
            status = "OK " if r["ok"] else "FAIL"
            print(f"[{status}] {r['slug']}")
            if not r["ok"]:
                print("   ", r.get("error", r.get("stdout", ""))[-600:])
        print(f"\n{ok_count}/{len(slugs)} built")
        return
    for slug in args:
        r = build(slug)
        print("OK " if r["ok"] else "FAIL", slug)
        if not r["ok"]:
            print("   ", r.get("error", r.get("stdout", ""))[-1000:])
        else:
            print("   ", r["stdout"].splitlines()[-1])


if __name__ == "__main__":
    main()

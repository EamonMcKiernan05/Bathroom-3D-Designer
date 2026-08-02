"""Headless batch model generation — the documented batch path (doc 03 §5.2).

Run with Blender's bundled Python via:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background --python blender_headless.py [-- slug1 slug2 ...]

With no args, builds every model in BUILDERS.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import blender_lib  # noqa: E402  (imports bpy — must run inside Blender)

ALL = [
    "toilet", "basin", "bath", "shower-tray", "shower-screen", "radiator",
    "towel-rail", "mirror", "cabinet", "vanity-unit", "tap", "shower-head",
    "shower-set", "shelf", "towel-ring", "robe-hook", "soap-dish",
]

argv = sys.argv
if "--" in argv:
    slugs = argv[argv.index("--") + 1:]
else:
    slugs = ALL

ok = 0
for slug in slugs:
    try:
        blender_lib.run_build(slug)
        ok += 1
        print(f"[OK] {slug}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[FAIL] {slug}: {e}")

print(f"BATCH_DONE {ok}/{len(slugs)}")

import { useCallback, useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { Canvas, useThree, type ThreeEvent } from '@react-three/fiber';
import { Html, Line } from '@react-three/drei';
import { Room, wallTopProfile } from './Room';
import { cornerHeightsFor, useDesignStore } from '../../stores/design-store';
import { useEditorStore } from '../../stores/editor-store';
import { topHeightAt } from '../../three/wallGeometry';
import { cornerAnglesDeg } from '../../lib/geometry';
import type { WallSpec } from '../../lib/types';

const HANDLE_COLOR = '#f59e0b'; // corners
const POINT_COLOR = '#38bdf8'; // intermediate top points
const LINE_COLOR = '#f59e0b';

/** Inward-pointing frame for a wall spec's straight centreline. */
function frameFrom(a: [number, number], b: [number, number], floor: [number, number][]) {
  const dx = b[0] - a[0], dz = b[1] - a[1];
  const len = Math.hypot(dx, dz) || 1;
  const ux = dx / len, uz = dz / len;
  let nx = -uz, nz = ux;
  // inward: toward the polygon centroid
  let cx = 0, cz = 0;
  for (const [px, pz] of floor) { cx += px; cz += pz; }
  cx /= Math.max(1, floor.length);
  cz /= Math.max(1, floor.length);
  const midx = (a[0] + b[0]) / 2, midz = (a[1] + b[1]) / 2;
  if (nx * (cx - midx) + nz * (cz - midz) < 0) { nx = -nx; nz = -nz; }
  return { u: [ux, uz] as [number, number], n: [nx, nz] as [number, number], len };
}

/** Raycast a screen point onto the wall's vertical plane (through the centreline). */
function raycastToWall(
  clientX: number,
  clientY: number,
  camera: THREE.Camera,
  el: HTMLElement,
  a: [number, number],
  u: [number, number],
  n: [number, number],
): { u: number; y: number } | null {
  const rect = el.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((clientX - rect.left) / rect.width) * 2 - 1,
    -((clientY - rect.top) / rect.height) * 2 + 1,
  );
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(ndc, camera);
  const plane = new THREE.Plane(new THREE.Vector3(n[0], 0, n[1]), -(n[0] * a[0] + n[1] * a[1]));
  const hit = new THREE.Vector3();
  if (!raycaster.ray.intersectPlane(plane, hit)) return null;
  return { u: (hit.x - a[0]) * u[0] + (hit.z - a[1]) * u[1], y: hit.y };
}

/** Frames the selected wall face-on, filling ~75% of the canvas. */
function FaceCamera({ wall }: { wall: WallSpec | null }) {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) ?? null;
  const size = useThree((s) => s.size);
  const room = useDesignStore((s) => s.design.room);
  const wallId = wall?.id ?? null;
  useEffect(() => {
    if (!wall) return;
    const a = wall.outline[0];
    const b = wall.outline[wall.outline.length - 1];
    const fr = frameFrom(a, b, room.floorPoints);
    const profile = wallTopProfile(wall, room.walls.indexOf(wall), room);
    const maxH = Math.max(...profile.map((p) => p.h), 500);
    const L = fr.len;
    const midX = (a[0] + b[0]) / 2;
    const midZ = (a[1] + b[1]) / 2;
    const fov = ((camera as THREE.PerspectiveCamera).fov ?? 50) * (Math.PI / 180);
    const aspect = size.width / Math.max(1, size.height);
    const dH = (maxH / 2) / Math.tan(fov / 2) / 0.72;
    const dW = (L / 2) / (Math.tan(fov / 2) * aspect) / 0.72;
    const dist = Math.max(dH, dW, 900) + 250;
    const ty = maxH * 0.5;
    camera.position.set(midX + fr.n[0] * dist, ty, midZ + fr.n[1] * dist);
    camera.lookAt(midX, ty, midZ);
    camera.updateProjectionMatrix();
    // OrbitControls (drei) registers after us via set({ controls }) and then
    // calls update() every frame, which lookAt()s the default target and would
    // pitch the camera off-axis. Re-run the framing once controls exist so the
    // face-on view and the orbit target stick.
    if (controls) {
      (controls as unknown as { target: THREE.Vector3; update: () => void }).target.set(midX, ty, midZ);
      (controls as unknown as { update: () => void }).update();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wallId, size.width, size.height, controls]);
  return null;
}

function WallFaceContents() {
  const room = useDesignStore((s) => s.design.room);
  const walls = room.walls || [];
  const selectedWallId = useEditorStore((s) => s.selectedWallId) ?? null;
  const setSelectedWall = useEditorStore((s) => s.setSelectedWall);
  const setCornerHeight = useDesignStore((s) => s.setCornerHeight);
  const moveTopPoint = useDesignStore((s) => s.moveTopPoint);
  const addTopPoint = useDesignStore((s) => s.addTopPoint);
  const removeTopPoint = useDesignStore((s) => s.removeTopPoint);
  const beginEdit = useDesignStore((s) => s.beginEdit);
  const commitEdit = useDesignStore((s) => s.commitEdit);

  const { camera, gl } = useThree();
  const camControls = (useThree((s) => s.controls) ?? null) as { enabled: boolean } | null;
  const glEl = gl.domElement;

  const selIdx = Math.max(0, walls.findIndex((w) => w.id === selectedWallId));
  const wall = walls[selIdx] ?? null;

  const fr = useMemo(
    () => (wall ? frameFrom(wall.outline[0], wall.outline[wall.outline.length - 1], room.floorPoints) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [wall?.id, room.floorPoints],
  );
  const profile = useMemo(
    () => (wall ? wallTopProfile(wall, selIdx, room) : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [wall?.id, room.cornerHeights, wall?.topPoints],
  );
  const L = fr?.len ?? 1;
  const T = wall?.thickness ?? 100;
  const cornerHeights = cornerHeightsFor(room);
  const editable = wall?.profile === 'rectangle' || wall?.profile === 'gable';

  // only render the focused wall + its two neighbours; everything else is hidden
  const visibleWallIds = useMemo(() => {
    const s = new Set<string>();
    if (!wall) return s;
    const n = walls.length;
    s.add(wall.id);
    for (const d of [-1, 1]) {
      const w = walls[(selIdx + d + n) % n];
      if (w) s.add(w.id);
    }
    return s;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wall?.id, walls.length]);

  const dragRef = useRef<{ kind: 'corner' | 'point'; index: number } | null>(null);
  const downPos = useRef<[number, number] | null>(null);

  const startDrag = useCallback(
    (kind: 'corner' | 'point', index: number, e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      if (!wall || !fr) return;
      dragRef.current = { kind, index };
      downPos.current = [e.clientX, e.clientY];
      if (camControls) camControls.enabled = false;
      beginEdit();
      const move = (ev: PointerEvent) => {
        const d = dragRef.current;
        if (!d || !fr) return;
        const hit = raycastToWall(ev.clientX, ev.clientY, camera, glEl, wall!.outline[0], fr.u, fr.n);
        if (!hit) return;
        if (d.kind === 'corner') {
          // corners: height only (shared with adjacent walls)
          const y = Math.max(100, Math.min(6000, Math.round(hit.y / 5) * 5));
          setCornerHeight(d.index, y);
        } else {
          // blue points: free drag — along the wall (u) AND height
          moveTopPoint(wall!.id, d.index, hit.u, hit.y);
        }
      };
      const up = () => {
        dragRef.current = null;
        commitEdit();
        if (camControls) camControls.enabled = true;
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    },
    [wall, fr, camera, glEl, camControls, beginEdit, commitEdit, setCornerHeight, moveTopPoint],
  );

  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      const down = downPos.current;
      if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return; // was a drag/orbit
      const surf = (e.object as THREE.Object3D).userData?.surface;
      const wix = (e.object as THREE.Object3D).userData?.wallIndex as number | undefined;
      if (surf === 'wall' && wix != null && walls[wix]) {
        e.stopPropagation();
        setSelectedWall(walls[wix].id);
      }
    },
    [walls, setSelectedWall],
  );

  const handleContextMenu = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      const surf = (e.object as THREE.Object3D).userData?.surface;
      const wix = (e.object as THREE.Object3D).userData?.wallIndex as number | undefined;
      if (surf !== 'wall' || wix !== selIdx || !wall || !fr) return;
      const hit = raycastToWall(e.clientX, e.clientY, camera, glEl, wall.outline[0], fr.u, fr.n);
      if (!hit) return;
      const topH = topHeightAt(profile, Math.max(0, Math.min(L, hit.u)));
      if (Math.abs(hit.y - topH) > 200) return; // only along the top edge
      addTopPoint(wall.id, Math.max(0, Math.min(L, hit.u)), topH);
    },
    [selIdx, wall, fr, camera, glEl, profile, L, addTopPoint],
  );

  // profile points in world space (slightly proud of the inner face)
  const worldPts = useMemo(() => {
    if (!wall || !fr) return [];
    const off = T / 2 + 25;
    return profile.map((p) => [
      wall.outline[0][0] + fr.u[0] * p.u + fr.n[0] * off,
      p.h,
      wall.outline[0][1] + fr.u[1] * p.u + fr.n[1] * off,
    ] as [number, number, number]);
  }, [wall, fr, profile, T]);

  const ca = wall?.cornerA ?? selIdx;
  const cb = wall?.cornerB ?? (selIdx + 1) % Math.max(1, room.floorPoints.length);
  // corner angles at both wall ends — visual only, never edited
  const cornerAngles = useMemo(
    () => (room.closed && room.floorPoints.length >= 3 ? cornerAnglesDeg(room.floorPoints) : []),
    [room.floorPoints, room.closed],
  );

  return (
    <>
      <ambientLight intensity={1.0} />
      <directionalLight position={[3000, 6000, 2000]} intensity={1.2} />
      <directionalLight position={[-3000, 5000, -2000]} intensity={0.7} />

      <FaceCamera wall={wall} />

      <group onClick={handleClick} onContextMenu={handleContextMenu}>
        <Room showCeiling={false} visibleWallIds={visibleWallIds} />
      </group>

      {/* top profile editing UI (focused wall only) */}
      {editable && wall && fr && (
        <group>
          <Line
            points={worldPts}
            color={LINE_COLOR}
            lineWidth={3}
            position={[0, 0, 0]}
          />
          {profile.map((p, i) => {
            const isCorner = i === 0 || i === profile.length - 1;
            const cornerIndex = i === 0 ? ca : i === profile.length - 1 ? cb : -1;
            const pointIndex = isCorner ? -1 : i - 1;
            const pos = worldPts[i];
            return (
              <group key={i}>
                <mesh
                  position={pos}
                  onPointerDown={(e) => {
                    e.stopPropagation();
                    if (isCorner) startDrag('corner', cornerIndex, e);
                    else startDrag('point', pointIndex, e);
                  }}
                  onDoubleClick={(e) => {
                    if (isCorner) return;
                    e.stopPropagation();
                    removeTopPoint(wall.id, pointIndex);
                  }}
                  onPointerOver={() => (glEl.style.cursor = isCorner ? 'ns-resize' : 'move')}
                  onPointerOut={() => (glEl.style.cursor = '')}
                >
                  <sphereGeometry args={[isCorner ? 90 : 70, 16, 12]} />
                  <meshBasicMaterial color={isCorner ? HANDLE_COLOR : POINT_COLOR} />
                </mesh>
                <Html position={[pos[0], pos[1] + 160, pos[2]]} center style={{ pointerEvents: 'none' }}>
                  <div
                    style={{
                      background: isCorner ? 'rgba(245,158,11,0.95)' : 'rgba(56,189,248,0.95)',
                      color: '#fff',
                      padding: '1px 6px',
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {Math.round(p.h)} mm
                    {isCorner && cornerAngles[cornerIndex] != null && (
                      <span style={{ opacity: 0.85, fontWeight: 500 }}> · {Math.round(cornerAngles[cornerIndex])}°</span>
                    )}
                  </div>
                </Html>
              </group>
            );
          })}
        </group>
      )}
    </>
  );
}

export function WallFaceEditor() {
  const room = useDesignStore((s) => s.design.room);
  const walls = room.walls || [];
  const selectedWallId = useEditorStore((s) => s.selectedWallId) ?? null;
  const setSelectedWall = useEditorStore((s) => s.setSelectedWall);
  const selected = walls.find((w) => w.id === selectedWallId) ?? walls[0] ?? null;

  return (
    <div
      className="relative h-full w-full"
      onContextMenu={(e) => e.preventDefault()}
    >
      <Canvas
        shadows={false}
        dpr={[1, 2]}
        gl={{ antialias: true, preserveDrawingBuffer: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.0 }}
        camera={{ position: [2500, 1500, 2500], fov: 50, near: 10, far: 100000 }}
      >
        <WallFaceContents />
      </Canvas>

      {/* wall picker */}
      <div className="absolute left-4 top-4 z-10 max-h-[60%] overflow-y-auto rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs shadow-sm">
        <div className="mb-1 font-semibold text-neutral-700">Walls ({walls.length})</div>
        {walls.map((w, i) => {
          const a = w.outline[0];
          const b = w.outline[w.outline.length - 1];
          const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
          const active = w.id === (selected?.id ?? '');
          return (
            <div
              key={w.id}
              onClick={() => setSelectedWall(w.id)}
              className={`mb-0.5 cursor-pointer rounded px-1.5 py-0.5 ${active ? 'bg-amber-100 text-amber-900' : 'text-neutral-600 hover:bg-neutral-100'}`}
            >
              {i + 1}. {Math.round(len)} mm
            </div>
          );
        })}
      </div>

      {/* hint */}
      <div className="pointer-events-none absolute bottom-4 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded-full bg-black/70 px-4 py-1.5 text-xs text-white">
        Drag amber corners up/down to slope the wall · right-click the top edge to add a point · drag blue points in any direction · double-click a blue point to delete it · click a wall to switch
      </div>
    </div>
  );
}

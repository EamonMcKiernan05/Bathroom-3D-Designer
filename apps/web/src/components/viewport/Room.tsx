import { useMemo } from 'react';
import * as THREE from 'three';
import { useLoader } from '@react-three/fiber';
import { polygonCentroid } from '../../lib/geometry';
import { cornerHeightsFor, useDesignStore } from '../../stores/design-store';
import type { TextureAssignment, TopPoint, WallSpec } from '../../lib/types';
import { configureTextureMaterial, tileShapeUVs } from '../../lib/texture-utils';
import { computeWallPieces, shapedWallMeshes, topPrismGeometry } from '../../three/wallGeometry';
import type { LocalFrame, TopProfilePoint } from '../../three/wallGeometry';

function useSurfaceMaterial(
  assignment: TextureAssignment | null,
  fallbackColor = '#f2f1ee',
  opts: { doubleSide?: boolean } = {},
) {
  const isSolid = !!assignment?.solidColor;
  const map =
    assignment && !isSolid && assignment.url ? useLoader(THREE.TextureLoader, assignment.url) : null;
  return useMemo(() => {
    if (isSolid && assignment?.solidColor) {
      const mat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(assignment.solidColor),
        roughness: 0.7,
        metalness: 0,
        side: opts.doubleSide ? THREE.DoubleSide : THREE.FrontSide,
      });
      return mat;
    }
    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(fallbackColor),
      roughness: 0.85,
      metalness: 0,
      side: opts.doubleSide ? THREE.DoubleSide : THREE.FrontSide,
    });
    if (map && assignment) {
      configureTextureMaterial(mat, map, assignment);
    }
    return mat;
  }, [isSolid, assignment?.solidColor, map, assignment?.url, assignment?.layout, assignment?.rotation, assignment?.groutWidthMm, fallbackColor, opts.doubleSide]);
}

/** Full top profile of a wall: corner heights (shared with neighbours) + its own intermediate points. */
export function wallTopProfile(spec: WallSpec, idx: number, room: {
  floorPoints: [number, number][];
  cornerHeights?: number[];
  ceilingHeight: number;
}): TopProfilePoint[] {
  const a = spec.outline[0];
  const b = spec.outline[spec.outline.length - 1];
  const L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  const ch = room.cornerHeights ?? [];
  const n = room.floorPoints.length;
  const ca = spec.cornerA ?? idx;
  const cb = spec.cornerB ?? (idx + 1) % n;
  const hA = ch[ca] ?? spec.height;
  const hB = ch[cb] ?? spec.height;
  const mids: TopPoint[] = (spec.topPoints ?? [])
    .map((p) => ({ u: Math.max(1, Math.min(L - 1, p.u)), h: p.h }))
    .sort((x, y) => x.u - y.u);
  return [{ u: 0, h: hA }, ...mids, { u: L, h: hB }];
}

interface OpeningSlice {
  pos: number;
  width: number;
  height: number;
  sill: number;
  type: string;
}

interface WallSegmentProps {
  wallIndex: number;
  a: [number, number];
  b: [number, number];
  length: number;
  u: [number, number];
  n: [number, number];
  thickness: number;
  topProfile: TopProfilePoint[];
  openings: OpeningSlice[];
  texture: TextureAssignment | null;
  selected: boolean;
  ghost?: boolean;
}

function WallSegment({ wallIndex, a, b, length: L, u, n, thickness: T, topProfile, openings, texture, selected, ghost }: WallSegmentProps) {
  const innerMat = useSurfaceMaterial(texture, undefined, { doubleSide: true });
  const plainMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#d8d6d1',
        roughness: 0.9,
        metalness: 0,
        side: THREE.DoubleSide,
      }),
    [],
  );
  const ghostMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#ffffff',
        roughness: 0.9,
        metalness: 0,
        transparent: true,
        opacity: 0.12,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    [],
  );

  const fr: LocalFrame = useMemo(() => ({ ux: u[0], uz: u[1], nx: n[0], nz: n[1], len: L }), [u, n, L]);
  const maxH = useMemo(() => Math.max(...topProfile.map((p) => p.h), 1), [topProfile]);
  const flat = useMemo(() => topProfile.every((p) => Math.abs(p.h - topProfile[0].h) < 1), [topProfile]);
  const topCapGeom = useMemo(() => new THREE.BoxGeometry(T, 4, L), [T, L]);

  const pieces = useMemo(() => computeWallPieces(L, topProfile, openings), [L, topProfile, openings]);

  // UV divisor: tile size + grout adjustment (grout baked into the texture image)
  const tw = (texture?.tileWidthMm ?? 600) + (texture?.groutWidthMm ?? 3) - 3;
  const th = (texture?.tileHeightMm ?? 300) + (texture?.groutWidthMm ?? 3) - 3;

  const geoms = useMemo(
    () =>
      pieces.map((p) => ({
        piece: p,
        geo: topPrismGeometry(a, b, fr, T, p, topProfile, { tw, th }),
        key: `w${wallIndex}-${p.u0.toFixed(0)}-${p.u1.toFixed(0)}-${p.y0.toFixed(0)}-${p.topFlat?.toFixed(0) ?? 't'}`,
      })),
    [pieces, a, b, fr, T, topProfile, tw, th, wallIndex],
  );

  const material = ghost ? ghostMat : [innerMat, plainMat];

  return (
    <>
      {/* piece boxes: topPrismGeometry vertices are ABSOLUTE world coords, so no group offset */}
      <group userData={{ surface: 'wall', wallIndex, clickable: true }}>
        {geoms.map(({ geo, key }) => (
          <mesh key={key} geometry={geo} material={material} userData={{ surface: 'wall', wallIndex, clickable: true }} />
        ))}
      </group>

      {/* cap + tint: positioned relative to the wall origin a */}
      <group position={[a[0], 0, a[1]]} userData={{ surface: 'wall', wallIndex, clickable: true }}>
        {/* top cap: thin box along the wall — only when the top is perfectly flat */}
        {!ghost && flat && (
          <mesh
            geometry={topCapGeom}
            material={plainMat}
            position={[u[0] * (L / 2), topProfile[0].h, u[1] * (L / 2)]}
            rotation={[0, Math.atan2(u[0], u[1]), 0]}
            userData={{ surface: 'wall', wallIndex, clickable: true }}
          />
        )}

        {/* selection tint */}
        {!ghost && selected && (
          <mesh position={[u[0] * (L / 2), maxH / 2, u[1] * (L / 2)]} userData={{ surface: 'wall', wallIndex, clickable: true }}>
            <boxGeometry args={[L + 4, maxH + 4, T + 4]} />
            <meshBasicMaterial color="#38bdf8" transparent opacity={0.25} depthWrite={false} />
          </mesh>
        )}
      </group>
    </>
  );
}

export function Room({
  ghostWallIds,
  showCeiling = true,
  visibleWallIds,
}: {
  /** walls to render as translucent ghost (blocking view but not the focus) */
  ghostWallIds?: Set<string>;
  showCeiling?: boolean;
  /** when set, only these walls render (others skipped entirely) */
  visibleWallIds?: Set<string>;
}) {
  const room = useDesignStore((s) => s.design.room);
  const doors = useDesignStore((s) => s.design.doors);
  const windows = useDesignStore((s) => s.design.windows);
  const wallTextures = useDesignStore((s) => s.design.wallTextures);
  const floorTexture = useDesignStore((s) => s.design.floorTexture);
  const ceilingTexture = useDesignStore((s) => s.design.ceilingTexture);
  const selectedSurface = useDesignStore((s) => s.selectedSurface);
  const selectSurface = useDesignStore((s) => s.selectSurface);

  const { floorPoints, ceilingHeight: H, wallThickness: T, closed } = room;
  const wallSpecs = room.walls || [];
  const cornerHeights = cornerHeightsFor(room);

  const floorGeom = useMemo(() => {
    if (floorPoints.length < 3) return null;
    const shape = new THREE.Shape();
    shape.moveTo(floorPoints[0][0], floorPoints[0][1]);
    for (let i = 1; i < floorPoints.length; i++) shape.lineTo(floorPoints[i][0], floorPoints[i][1]);
    shape.closePath();
    const g = new THREE.ShapeGeometry(shape);
    g.rotateX(-Math.PI / 2);
    const minX = Math.min(...floorPoints.map((p) => p[0]));
    const minZ = Math.min(...floorPoints.map((p) => p[1]));
    const tw = (floorTexture?.tileWidthMm ?? 600) + (floorTexture?.groutWidthMm ?? 3) - 3;
    const th = (floorTexture?.tileHeightMm ?? 600) + (floorTexture?.groutWidthMm ?? 3) - 3;
    tileShapeUVs(g, minX, minZ, tw, th);
    return g;
  }, [floorPoints, floorTexture]);

  const floorMat = useSurfaceMaterial(floorTexture, '#e5e4e0');

  const ceilingGeom = useMemo(() => {
    if (floorPoints.length < 3) return null;
    const shape = new THREE.Shape();
    shape.moveTo(floorPoints[0][0], floorPoints[0][1]);
    for (let i = 1; i < floorPoints.length; i++) shape.lineTo(floorPoints[i][0], floorPoints[i][1]);
    shape.closePath();
    const g = new THREE.ShapeGeometry(shape);
    g.rotateX(Math.PI / 2);
    const minX = Math.min(...floorPoints.map((p) => p[0]));
    const minZ = Math.min(...floorPoints.map((p) => p[1]));
    const tw = (ceilingTexture?.tileWidthMm ?? 600) + (ceilingTexture?.groutWidthMm ?? 3) - 3;
    const th = (ceilingTexture?.tileHeightMm ?? 600) + (ceilingTexture?.groutWidthMm ?? 3) - 3;
    tileShapeUVs(g, minX, minZ, tw, th);
    return g;
  }, [floorPoints, ceilingTexture]);

  const ceilingMat = useSurfaceMaterial(ceilingTexture, '#f8f8f6');

  return (
    <group>
      {floorGeom && (
        <mesh geometry={floorGeom} material={floorMat} position={[0, 0, 0]} userData={{ surface: 'floor', clickable: true }} />
      )}

      {wallSpecs.map((spec, wi) => {
        if (visibleWallIds && !visibleWallIds.has(spec.id)) return null;
        const a = spec.outline[0];
        const b = spec.outline[spec.outline.length - 1];
        const fr = frameFrom(a, b, floorPoints);
        const ops: OpeningSlice[] = [];
        for (const d of doors) if (d.wallIndex === wi) ops.push({ pos: d.pos, width: d.width, height: d.height, sill: 0, type: 'door' });
        for (const win of windows) if (win.wallIndex === wi) ops.push({ pos: win.pos, width: win.width, height: win.height, sill: win.sillHeight, type: 'window' });
        const isGhost = !!ghostWallIds?.has(spec.id);
        const selected = !isGhost && selectedSurface?.type === 'wall' && selectedSurface.index === wi;

        if (spec.profile === 'rectangle') {
          return (
            <WallSegment
              key={spec.id}
              wallIndex={wi}
              a={a}
              b={b}
              length={fr.length}
              u={fr.u}
              n={fr.n}
              thickness={spec.thickness || T}
              topProfile={wallTopProfile(spec, wi, room)}
              openings={ops}
              texture={isGhost ? null : (wallTextures[wi] ?? null)}
              selected={selected}
              ghost={isGhost}
            />
          );
        }
        return (
          <ShapedWall
            key={spec.id}
            spec={spec}
            selected={selected}
            ghost={isGhost}
            onClick={() => selectSurface({ type: 'wall', index: wi })}
          />
        );
      })}

      {showCeiling && ceilingGeom && (
        <mesh geometry={ceilingGeom} material={ceilingMat} position={[0, H, 0]} userData={{ surface: 'ceiling', clickable: true }} />
      )}

      {/* Corner posts: fill the exterior corner voids left between two wall end caps.
          Only for plain rectangle rooms — shaped walls carry their own geometry. */}
      {!ghostWallIds &&
        wallSpecs.every((w) => w.profile === 'rectangle') &&
        floorPoints.map((p, i) => {
          const h = cornerHeights[i] ?? H;
          const prev = floorPoints[(i - 1 + floorPoints.length) % floorPoints.length];
          const dx = p[0] - prev[0];
          const dz = p[1] - prev[1];
          const len = Math.hypot(dx, dz) || 1;
          return (
            <mesh key={`corner-${i}`} position={[p[0], h / 2, p[1]]} rotation={[0, Math.atan2(dx / len, dz / len), 0]}>
              <boxGeometry args={[T, h, T]} />
              <meshStandardMaterial color="#d8d6d1" roughness={0.9} />
            </mesh>
          );
        })}

      {/* Openings are plain holes cut into the solid wall boxes — the reveal faces
          (jambs / sill / head) carry the wall's own thickness. */}
    </group>
  );
}

/** Inward-pointing frame for a wall spec's straight centreline. */
function frameFrom(a: [number, number], b: [number, number], floor: [number, number][]) {
  const dx = b[0] - a[0], dz = b[1] - a[1];
  const len = Math.hypot(dx, dz) || 1;
  const ux = dx / len, uz = dz / len;
  let nx = -uz, nz = ux;
  const [cx, cz] = polygonCentroid(floor);
  const midx = (a[0] + b[0]) / 2, midz = (a[1] + b[1]) / 2;
  if (nx * (cx - midx) + nz * (cz - midz) < 0) {
    nx = -nx;
    nz = -nz;
  }
  return { a, b, length: len, u: [ux, uz] as [number, number], n: [nx, nz] as [number, number] };
}

/** Renders a non-rectangle wall (gable / stairs / boxing) from its parametric shape. */
function ShapedWall({
  spec,
  selected,
  ghost,
  onClick,
}: {
  spec: WallSpec;
  selected: boolean;
  ghost?: boolean;
  onClick: () => void;
}) {
  const meshes = useMemo(() => shapedWallMeshes(spec), [spec]);
  const mat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: ghost ? '#ffffff' : '#cfcac3',
        roughness: 0.9,
        metalness: 0,
        side: THREE.DoubleSide,
        transparent: !!ghost,
        opacity: ghost ? 0.12 : 1,
        depthWrite: !ghost,
      }),
    [ghost],
  );
  return (
    <group userData={{ surface: 'wall', clickable: true }} onClick={(e) => {
      e.stopPropagation();
      onClick();
    }}>
      {meshes.map((m, i) => (
        <mesh key={i} geometry={m.geo} material={mat} position={m.position} userData={{ surface: 'wall', clickable: true }} />
      ))}
    </group>
  );
}

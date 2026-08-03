import { useMemo } from 'react';
import * as THREE from 'three';
import { useLoader } from '@react-three/fiber';
import { buildWalls } from '../../lib/geometry';
import { useDesignStore } from '../../stores/design-store';
import type { TextureAssignment, WallOpening } from '../../lib/types';
import { configureTextureMaterial, tilePlaneUVs, tileShapeUVs } from '../../lib/texture-utils';

function useSurfaceMaterial(
  assignment: TextureAssignment | null,
  fallbackColor = '#f2f1ee',
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
      });
      return mat;
    }
    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(fallbackColor),
      roughness: 0.85,
      metalness: 0,
    });
    if (map && assignment) {
      configureTextureMaterial(mat, map, assignment);
    }
    return mat;
  }, [isSolid, assignment?.solidColor, map, assignment?.url, assignment?.layout, assignment?.rotation, assignment?.groutWidthMm, fallbackColor]);
}

interface Piece {
  x0: number;
  x1: number; // along wall
  z0: number;
  z1: number; // height
}

/** Compute solid wall pieces by subtracting door/window openings (1D intervals). */
function computePieces(L: number, H: number, openings: { pos: number; width: number; height: number; sill: number }[]): Piece[] {
  const pieces: Piece[] = [];
  for (const o of openings) {
    const w0 = Math.max(0, o.pos - o.width / 2);
    const w1 = Math.min(L, o.pos + o.width / 2);
    // left
    if (w0 > 1) pieces.push({ x0: 0, x1: w0, z0: 0, z1: H });
    // right
    if (w1 < L - 1) pieces.push({ x0: w1, x1: L, z0: 0, z1: H });
    // below (window only, sill > 0)
    if (o.sill > 1) pieces.push({ x0: w0, x1: w1, z0: 0, z1: Math.min(o.sill, H) });
    // above
    const top = Math.min(H, o.sill + o.height);
    if (top < H - 1) pieces.push({ x0: w0, x1: w1, z0: top, z1: H });
  }
  if (openings.length === 0) pieces.push({ x0: 0, x1: L, z0: 0, z1: H });
  return pieces;
}

interface WallSegmentProps {
  wallIndex: number;
  a: [number, number];
  b: [number, number];
  length: number;
  u: [number, number];
  n: [number, number];
  thickness: number;
  height: number;
  openings: { pos: number; width: number; height: number; sill: number; type: string }[];
  texture: TextureAssignment | null;
  selected: boolean;
  onWallClick: (wallIndex: number, x: number, z: number) => void;
}

function WallSegment({ wallIndex, a, b, length: L, u, n, thickness: T, height: H, openings, texture, selected, onWallClick }: WallSegmentProps) {
  const innerMat = useSurfaceMaterial(texture);
  const outerMat = useSurfaceMaterial(null, '#d8d6d1');
  const capMat = useSurfaceMaterial(null, '#d8d6d1');

  const pieces = useMemo(() => computePieces(L, H, openings), [L, H, openings]);

  const innerRot = Math.atan2(n[0], n[1]); // +Z faces inward
  const outerRot = innerRot + Math.PI;
  const ax = a[0], az = a[1];

  // UV divisor: tile size + grout adjustment (grout baked into the texture image)
  const tw = (texture?.tileWidthMm ?? 600) + (texture?.groutWidthMm ?? 3) - 3;
  const th = (texture?.tileHeightMm ?? 300) + (texture?.groutWidthMm ?? 3) - 3;

  const innerPieces = useMemo(() => {
    return pieces.map((p) => {
      const w = p.x1 - p.x0;
      const h = p.z1 - p.z0;
      const geom = new THREE.PlaneGeometry(w, h);
      tilePlaneUVs(geom, w, h, tw, th);
      return { p, geom, key: `in-${wallIndex}-${p.x0.toFixed(0)}-${p.x1.toFixed(0)}-${p.z0.toFixed(0)}-${p.z1.toFixed(0)}` };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pieces, wallIndex, tw, th]);

  const outerPieces = useMemo(() => {
    return pieces.map((p) => {
      const w = p.x1 - p.x0;
      const h = p.z1 - p.z0;
      const geom = new THREE.PlaneGeometry(w, h);
      return { p, geom, key: `out-${wallIndex}-${p.x0.toFixed(0)}-${p.x1.toFixed(0)}-${p.z0.toFixed(0)}-${p.z1.toFixed(0)}` };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    });
  }, [pieces, wallIndex]);

  const capGeom = useMemo(() => new THREE.PlaneGeometry(T, L), [T, L]);
  const topCapGeom = useMemo(() => new THREE.PlaneGeometry(L, T), [L, T]);

  return (
    <group position={[ax, 0, az]}>
      {/* inner face pieces (room side, textured) */}
      {innerPieces.map(({ p, geom, key }) => {
        const w = p.x1 - p.x0;
        const h = p.z1 - p.z0;
        const cx = (p.x0 + p.x1) / 2;
        const cz = (p.z0 + p.z1) / 2;
        return (
          <mesh
            key={key}
            geometry={geom}
            material={innerMat}
            position={[u[0] * cx + n[0] * (T / 2 + 0.5), cz, u[1] * cx + n[1] * (T / 2 + 0.5)]}
            rotation={[0, innerRot, 0]}
            userData={{ surface: 'wall', wallIndex, clickable: true }}
          />
        );
      })}

      {/* outer face (plain) */}
      {outerPieces.map(({ p, geom, key }) => {
        const cx = (p.x0 + p.x1) / 2;
        const cz = (p.z0 + p.z1) / 2;
        return (
          <mesh
            key={key}
            geometry={geom}
            material={outerMat}
            position={[u[0] * cx - n[0] * (T / 2 + 0.5), cz, u[1] * cx - n[1] * (T / 2 + 0.5)]}
            rotation={[0, outerRot, 0]}
          />
        );
      })}

      {/* side caps */}
      <mesh geometry={capGeom} material={capMat} position={[0, H / 2, 0]} rotation={[0, Math.atan2(u[0], u[1]), Math.PI / 2]} />
      <mesh geometry={capGeom} material={capMat} position={[u[0] * L, H / 2, u[1] * L]} rotation={[0, Math.atan2(u[0], u[1]), Math.PI / 2]} />
      {/* top cap */}
      <mesh
        geometry={topCapGeom}
        material={capMat}
        position={[u[0] * (L / 2), H, u[1] * (L / 2)]}
        rotation={[Math.PI / 2, 0, Math.atan2(u[0], u[1])]}
      />
      {/* selection tint */}
      {selected && (
        <mesh position={[u[0] * (L / 2), H / 2, u[1] * (L / 2)]}>
          <boxGeometry args={[L + 4, H + 4, T + 4]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.25} depthWrite={false} />
        </mesh>
      )}
    </group>
  );
}

export function Room() {
  const room = useDesignStore((s) => s.design.room);
  const doors = useDesignStore((s) => s.design.doors);
  const windows = useDesignStore((s) => s.design.windows);
  const wallTextures = useDesignStore((s) => s.design.wallTextures);
  const floorTexture = useDesignStore((s) => s.design.floorTexture);
  const ceilingTexture = useDesignStore((s) => s.design.ceilingTexture);
  const selectedSurface = useDesignStore((s) => s.selectedSurface);
  const selectSurface = useDesignStore((s) => s.selectSurface);

  const { floorPoints, ceilingHeight: H, wallThickness: T, closed } = room;
  const walls = useMemo(() => (closed ? buildWalls(floorPoints) : []), [floorPoints, closed]);

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

      {walls.map((w) => {
        const ops: { pos: number; width: number; height: number; sill: number; type: string }[] = [];
        for (const d of doors) if (d.wallIndex === w.index) ops.push({ pos: d.pos, width: d.width, height: d.height, sill: 0, type: 'door' });
        for (const win of windows) if (win.wallIndex === w.index) ops.push({ pos: win.pos, width: win.width, height: win.height, sill: win.sillHeight, type: 'window' });
        return (
          <WallSegment
            key={w.index}
            wallIndex={w.index}
            a={w.a}
            b={w.b}
            length={w.length}
            u={w.u}
            n={w.n}
            thickness={T}
            height={H}
            openings={ops}
            texture={wallTextures[w.index] ?? null}
            selected={selectedSurface?.type === 'wall' && selectedSurface.index === w.index}
            onWallClick={(wi, x, z) => selectSurface({ type: 'wall', index: wi })}
          />
        );
      })}

      {ceilingGeom && (
        <mesh geometry={ceilingGeom} material={ceilingMat} position={[0, H, 0]} userData={{ surface: 'ceiling', clickable: true }} />
      )}

      <Openings />
    </group>
  );
}

/** Door leaf + window frame/glass rendered in front of the wall surface. */
function Openings() {
  const doors = useDesignStore((s) => s.design.doors);
  const windows = useDesignStore((s) => s.design.windows);
  const room = useDesignStore((s) => s.design.room);
  const walls = useMemo(() => (room.closed ? buildWalls(room.floorPoints) : []), [room]);

  if (!room.closed) return null;

  return (
    <group>
      {doors.map((d) => {
        const w = walls[d.wallIndex];
        if (!w) return null;
        const t = (d.pos - d.width / 2) / w.length;
        const hingeX = w.a[0] + w.u[0] * (d.pos - d.width / 2);
        const hingeZ = w.a[1] + w.u[1] * (d.pos - d.width / 2);
        return (
          <group key={d.id} position={[hingeX, 0, hingeZ]}>
            {/* door leaf, hinged at one side, opened ~65° */}
            <mesh position={[0, d.height / 2, 0]} rotation={[0, Math.atan2(w.u[0], w.u[1]) - Math.PI / 2 - 1.1, 0]}>
              <boxGeometry args={[d.width, d.height, 36]} />
              <meshStandardMaterial color="#cbb391" roughness={0.6} />
            </mesh>
            {/* frame: header */}
            <mesh position={[w.u[0] * (d.width / 2) + w.n[0] * 20, d.height + 20, w.u[1] * (d.width / 2) + w.n[1] * 20]}>
              <boxGeometry args={[d.width + 60, 40, 80]} />
              <meshStandardMaterial color="#efece6" roughness={0.7} />
            </mesh>
          </group>
        );
      })}

      {windows.map((win) => {
        const w = walls[win.wallIndex];
        if (!w) return null;
        const cx = w.a[0] + w.u[0] * win.pos;
        const cz = w.a[1] + w.u[1] * win.pos;
        const nOut = [-w.n[0], -w.n[1]] as [number, number];
        const rot = Math.atan2(nOut[0], nOut[1]);
        return (
          <group key={win.id} position={[cx, win.sillHeight + win.height / 2, cz]} rotation={[0, rot, 0]}>
            {/* glass */}
            <mesh position={[0, 0, -20]}>
              <planeGeometry args={[win.width, win.height]} />
              <meshStandardMaterial color="#bfe3f0" transparent opacity={0.55} roughness={0.05} metalness={0.1} side={THREE.DoubleSide} />
            </mesh>
            {/* frame */}
            <mesh position={[0, 0, -24]}>
              <boxGeometry args={[win.width + 70, 30, 50]} />
              <meshStandardMaterial color="#efece6" roughness={0.7} />
            </mesh>
            <mesh position={[0, 0, -24]}>
              <boxGeometry args={[30, win.height + 70, 50]} />
              <meshStandardMaterial color="#efece6" roughness={0.7} />
            </mesh>
            {/* sill */}
            <mesh position={[0, -win.height / 2 - 12, 8]}>
              <boxGeometry args={[win.width + 90, 24, 140]} />
              <meshStandardMaterial color="#efece6" roughness={0.7} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

// 2D polygon geometry for rooms — all in millimetres (x, z plane)

export interface WallSeg {
  index: number;
  a: [number, number];
  b: [number, number];
  length: number;
  /** unit direction along the wall (a -> b) */
  u: [number, number];
  /** unit inward normal (pointing into the polygon) */
  n: [number, number];
  angle: number; // Y-rotation of the wall direction
}

export function polygonCentroid(pts: [number, number][]): [number, number] {
  let x = 0, z = 0;
  for (const [px, pz] of pts) { x += px; z += pz; }
  return [x / Math.max(1, pts.length), z / Math.max(1, pts.length)];
}

export function buildWalls(pts: [number, number][]): WallSeg[] {
  const walls: WallSeg[] = [];
  const [cx, cz] = polygonCentroid(pts);
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const a = pts[i];
    const b = pts[(i + 1) % n];
    const dx = b[0] - a[0];
    const dz = b[1] - a[1];
    const len = Math.hypot(dx, dz);
    if (len < 1) continue;
    const ux = dx / len, uz = dz / len;
    // inward normal: for a CCW polygon the inward normal is (-uz, ux)
    let nx = -uz, nz = ux;
    // ensure inward: check against polygon centroid
    const midx = (a[0] + b[0]) / 2;
    const midz = (a[1] + b[1]) / 2;
    const toCx = cx - midx, toCz = cz - midz;
    if (nx * toCx + nz * toCz < 0) { nx = -nx; nz = -nz; }
    walls.push({
      index: i,
      a, b,
      length: len,
      u: [ux, uz],
      n: [nx, nz],
      angle: Math.atan2(ux, uz), // Y-rotation that points +Z along u
    });
  }
  return walls;
}

export function pointInPolygon(px: number, pz: number, pts: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i][0], zi = pts[i][1];
    const xj = pts[j][0], zj = pts[j][1];
    if (zi > pz !== zj > pz && px < ((xj - xi) * (pz - zi)) / (zj - zi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/**
 * Interior corner angles (degrees) of a polygon, one per point.
 * Visual-only helper — the angle at each corner between its two edges (0..180).
 */
export function cornerAnglesDeg(pts: [number, number][]): number[] {
  const n = pts.length;
  if (n < 3) return pts.map(() => 0);
  return pts.map((p, i) => {
    const prev = pts[(i - 1 + n) % n];
    const next = pts[(i + 1) % n];
    const v1x = prev[0] - p[0], v1z = prev[1] - p[1];
    const v2x = next[0] - p[0], v2z = next[1] - p[1];
    const l1 = Math.hypot(v1x, v1z);
    const l2 = Math.hypot(v2x, v2z);
    if (l1 < 1e-6 || l2 < 1e-6) return 0;
    const dot = v1x * v2x + v1z * v2z;
    return (Math.acos(Math.max(-1, Math.min(1, dot / (l1 * l2)))) * 180) / Math.PI;
  });
}

export function distToSegment(px: number, pz: number, ax: number, az: number, bx: number, bz: number): number {
  const dx = bx - ax, dz = bz - az;
  const len2 = dx * dx + dz * dz;
  if (len2 === 0) return Math.hypot(px - ax, pz - az);
  let t = ((px - ax) * dx + (pz - az) * dz) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (ax + t * dx), pz - (az + t * dz));
}

export interface SnapResult {
  wallIndex: number;
  /** rotation (radians about Y) aligning item +Z with the wall inward normal */
  rotation: number;
  /** position on the wall line (back face of item flush with wall) */
  pos: [number, number, number];
}

/**
 * Snap a point to the nearest wall. Returns null when no wall within `threshold`.
 * `backOffset` = distance the item's back should sit from the wall line (0 = flush).
 */
export function snapToWall(
  x: number, z: number,
  pts: [number, number][],
  threshold: number,
  backOffset = 0,
): SnapResult | null {
  let best: SnapResult | null = null;
  let bestD = Infinity;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i];
    const b = pts[(i + 1) % pts.length];
    const d = distToSegment(x, z, a[0], a[1], b[0], b[1]);
    if (d < bestD) {
      bestD = d;
      const dx = b[0] - a[0], dz = b[1] - a[1];
      const len = Math.hypot(dx, dz);
      if (len < 1) continue;
      const ux = dx / len, uz = dz / len;
      let nx = -uz, nz = ux;
      const cx = 0, cz = 0;
      const midx = (a[0] + b[0]) / 2, midz = (a[1] + b[1]) / 2;
      if (nx * (cx - midx) + nz * (cz - midz) < 0) { nx = -nx; nz = -nz; }      // project point onto the segment line
      const t = Math.max(0, Math.min(1, ((x - a[0]) * dx + (z - a[1]) * dz) / (len * len)));
      const wx = a[0] + t * dx;
      const wz = a[1] + t * dz;
      const rot = Math.atan2(nx, nz);
      best = {
        wallIndex: i,
        rotation: rot,
        pos: [wx + nx * backOffset, 0, wz + nz * backOffset],
      };
    }
  }
  return bestD <= threshold ? best : null;
}

export function clampPointToPolygon(x: number, z: number, pts: [number, number][]): [number, number] {
  if (pointInPolygon(x, z, pts)) return [x, z];
  let bestD = Infinity;
  let best: [number, number] = [x, z];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i];
    const b = pts[(i + 1) % pts.length];
    const dx = b[0] - a[0], dz = b[1] - a[1];
    const len2 = dx * dx + dz * dz;
    let t = ((x - a[0]) * dx + (z - a[1]) * dz) / len2;
    t = Math.max(0, Math.min(1, t));
    const px = a[0] + t * dx, pz = a[1] + t * dz;
    const d = Math.hypot(x - px, z - pz);
    if (d < bestD) { bestD = d; best = [px, pz]; }
  }
  return best;
}

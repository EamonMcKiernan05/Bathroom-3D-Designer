import * as THREE from 'three';
import type { WallSpec } from '../lib/types';

type V3 = [number, number, number];

function quad(pos: number[], norm: number[], a: V3, b: V3, c: V3, d: V3) {
  const ab: V3 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
  const ac: V3 = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
  const n = [
    ab[1] * ac[2] - ab[2] * ac[1],
    ab[2] * ac[0] - ab[0] * ac[2],
    ab[0] * ac[1] - ab[1] * ac[0],
  ];
  const l = Math.hypot(n[0], n[1], n[2]) || 1;
  const nn = [n[0] / l, n[1] / l, n[2] / l];
  for (const p of [a, b, c, c, d, a]) {
    pos.push(...p);
    norm.push(...nn);
  }
}

/**
 * Prism from wall segment a->b (centreline), thickness t, top height hA at end a
 * and hB at end b (hA == hB gives a plain rectangle; differing heights gives a
 * sloped-top wall, e.g. under a pitched ceiling / gable). Flat-shaded, doubleside-safe.
 */
export function prismGeometry(a: [number, number], b: [number, number], t: number, hA: number, hB: number): THREE.BufferGeometry {
  const dx = b[0] - a[0], dz = b[1] - a[1];
  const len = Math.hypot(dx, dz) || 1;
  const ux = dx / len, uz = dz / len;
  const nx = -uz, nz = ux; // perpendicular to the wall

  const n2 = t / 2;
  // bottom corners (y=0) and top corners (y = hA / hB)
  const b0m: V3 = [a[0] - nx * n2, 0, a[1] - nz * n2];
  const b0p: V3 = [a[0] + nx * n2, 0, a[1] + nz * n2];
  const b1m: V3 = [b[0] - nx * n2, 0, b[1] - nz * n2];
  const b1p: V3 = [b[0] + nx * n2, 0, b[1] + nz * n2];
  const t0m: V3 = [a[0] - nx * n2, hA, a[1] - nz * n2];
  const t0p: V3 = [a[0] + nx * n2, hA, a[1] + nz * n2];
  const t1m: V3 = [b[0] - nx * n2, hB, b[1] - nz * n2];
  const t1p: V3 = [b[0] + nx * n2, hB, b[1] + nz * n2];

  const pos: number[] = [];
  const norm: number[] = [];
  // bottom
  quad(pos, norm, b0p, b0m, b1m, b1p);
  // -n side
  quad(pos, norm, b0m, t0m, t1m, b1m);
  // +n side
  quad(pos, norm, b1p, t1p, t0p, b0p);
  // top
  quad(pos, norm, t0m, t0p, t1p, t1m);
  // end cap a
  quad(pos, norm, b0p, t0p, t0m, b0m);
  // end cap b
  quad(pos, norm, b1m, t1m, t1p, b1p);

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(norm, 3));
  return geo;
}

/** Step for the under-stairs wall: a single descending box. */
export function stepGeometry(a: [number, number], b: [number, number], t: number, hBottom: number, hTop: number): THREE.BufferGeometry {
  return prismGeometry(a, b, t, hBottom, hTop);
}

/** A small axis-aligned box geometry helper (kept for completeness). */
export function boxGeometry(w: number, h: number, d: number): THREE.BufferGeometry {
  return new THREE.BoxGeometry(w, h, d);
}

/** A solid box oriented along the wall frame: u = along wall (bl long), n = protrudes +n, y = boxTop high. */
export function orientedBoxGeometry(
  fr: LocalFrame,
  a: [number, number],
  from: number,
  bl: number,
  protrude: number,
  thickness: number,
  boxTop: number,
): THREE.BufferGeometry {
  const nIn = +thickness / 2; // inner edge of box on +n side (at the wall face)
  const nOut = nIn + protrude;
  const u0 = from;
  const u1 = from + bl;

  const P = (u: number, n: number, y: number): V3 => [
    a[0] + fr.ux * u + fr.nx * n,
    y,
    a[1] + fr.uz * u + fr.nz * n,
  ];
  const b00: V3 = P(u0, nIn, 0), b01: V3 = P(u0, nOut, 0);
  const b10: V3 = P(u1, nIn, 0), b11: V3 = P(u1, nOut, 0);
  const t00: V3 = P(u0, nIn, boxTop), t01: V3 = P(u0, nOut, boxTop);
  const t10: V3 = P(u1, nIn, boxTop), t11: V3 = P(u1, nOut, boxTop);

  const pos: number[] = [];
  const norm: number[] = [];
  quad(pos, norm, b01, b00, b10, b11); // bottom
  quad(pos, norm, b00, t00, t10, b10); // -n inner face
  quad(pos, norm, b11, t11, t01, b01); // +n outer face
  quad(pos, norm, t00, t01, t11, t10); // top
  quad(pos, norm, b00, b01, t01, t00); // end cap at u0
  quad(pos, norm, b11, b10, t10, t11); // end cap at u1
  return finalize(pos, norm);
}

function finalize(pos: number[], norm: number[]): THREE.BufferGeometry {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(norm, 3));
  return geo;
}

export interface LocalFrame {
  ux: number;
  uz: number;
  nx: number;
  nz: number;
  len: number;
}

/** Local frame (along and perpendicular) for a wall segment. */
export function wallFrame(a: [number, number], b: [number, number]): LocalFrame {
  const dx = b[0] - a[0], dz = b[1] - a[1];
  const len = Math.hypot(dx, dz) || 1;
  const ux = dx / len, uz = dz / len;
  return { ux, uz, nx: -uz, nz: ux, len };
}

// ---------------------------------------------------------------------------
// Solid wall pieces (with real depth) and custom top profiles
// ---------------------------------------------------------------------------

export interface TopProfilePoint {
  u: number; // mm along the wall (0..L)
  h: number; // mm height at that point
}

/** Height of a polyline top profile at u (linear interpolation, clamped). */
export function topHeightAt(profile: TopProfilePoint[], u: number): number {
  if (profile.length === 0) return 0;
  if (u <= profile[0].u) return profile[0].h;
  const last = profile[profile.length - 1];
  if (u >= last.u) return last.h;
  for (let i = 0; i < profile.length - 1; i++) {
    const a = profile[i], b = profile[i + 1];
    if (u >= a.u && u <= b.u) {
      const t = b.u - a.u === 0 ? 0 : (u - a.u) / (b.u - a.u);
      return a.h + (b.h - a.h) * t;
    }
  }
  return last.h;
}

/** Clip a top profile to the u-range [u0, u1], sampling boundary points. */
export function clipProfile(profile: TopProfilePoint[], u0: number, u1: number): TopProfilePoint[] {
  const out: TopProfilePoint[] = [];
  // sample at the boundaries (even if a breakpoint coincides, dedupe below)
  out.push({ u: u0, h: topHeightAt(profile, u0) });
  for (const p of profile) {
    if (p.u > u0 + 0.5 && p.u < u1 - 0.5) out.push({ u: p.u, h: p.h });
  }
  out.push({ u: u1, h: topHeightAt(profile, u1) });
  // dedupe + sort
  const sorted = out.sort((a, b) => a.u - b.u);
  return sorted.filter((p, i) => i === 0 || p.u - sorted[i - 1].u > 0.5);
}

/** One solid chunk of wall after subtracting door/window openings. */
export interface WallPiece {
  u0: number;
  u1: number; // along-wall extent (mm)
  y0: number; // flat bottom height
  topFlat: number | null; // flat top height, or null = follow the wall's top profile
}

/**
 * Partition a wall into solid pieces by subtracting door/window openings
 * (each a rectangle [pos±w/2] × [sill, sill+height] in (u, y) space).
 * topProfile spans the whole wall (0..L) and gives the top edge of "above"
 * pieces so sloped/pointed tops stay intact around openings.
 */
export function computeWallPieces(
  L: number,
  topProfile: TopProfilePoint[],
  openings: { pos: number; width: number; height: number; sill: number }[],
): WallPiece[] {
  // vertical strip boundaries: every opening edge
  const raw: number[] = [0, L];
  for (const o of openings) {
    raw.push(Math.max(0, o.pos - o.width / 2), Math.min(L, o.pos + o.width / 2));
  }
  raw.sort((a, b) => a - b);
  const xs: number[] = [];
  for (const v of raw) {
    if (xs.length === 0 || v - xs[xs.length - 1] > 0.5) xs.push(v);
  }
  if (xs[xs.length - 1] < L - 0.5) xs.push(L);

  const pieces: WallPiece[] = [];
  for (let k = 0; k < xs.length - 1; k++) {
    const s0 = xs[k], s1 = xs[k + 1];
    if (s1 - s0 < 1) continue;
    const covering = openings.filter((o) => o.pos - o.width / 2 <= s0 + 1 && o.pos + o.width / 2 >= s1 - 1);
    if (covering.length === 0) {
      pieces.push({ u0: s0, u1: s1, y0: 0, topFlat: null });
      continue;
    }
    // merge y-intervals of the openings covering this strip
    const ivals = covering
      .map((o) => [o.sill, o.sill + o.height] as [number, number])
      .sort((a, b) => a[0] - b[0]);
    const merged: [number, number][] = [];
    for (const iv of ivals) {
      const last = merged[merged.length - 1];
      if (last && iv[0] <= last[1] + 1) last[1] = Math.max(last[1], iv[1]);
      else merged.push([iv[0], iv[1]]);
    }
    const topMin = Math.min(topHeightAt(topProfile, s0), topHeightAt(topProfile, s1));
    let y = 0;
    for (const [ya, yb] of merged) {
      if (ya > y + 1) pieces.push({ u0: s0, u1: s1, y0: y, topFlat: ya });
      y = Math.max(y, yb);
    }
    if (y < topMin - 1) pieces.push({ u0: s0, u1: s1, y0: y, topFlat: null });
  }
  return pieces;
}

interface PushOpts {
  /** tiling for the inner (+n) face UVs, in mm; undefined = plain UVs */
  tw?: number;
  th?: number;
}

/**
 * Solid prism for one wall piece: flat bottom at y0, top edge following
 * `top` (a polyline already clipped to the piece's u-range). The +n face is
 * the room-side face and gets tiled UVs (material group 0); every other face
 * is plain (group 1). n must point INTO the room (inward normal).
 */
export function topPrismGeometry(
  a: [number, number],
  _b: [number, number],
  fr: LocalFrame,
  t: number,
  piece: WallPiece,
  top: TopProfilePoint[],
  opts: PushOpts = {},
): THREE.BufferGeometry {
  const n2 = t / 2;
  const P = (u: number, y: number, n: number): [number, number, number] => [
    a[0] + fr.ux * u + fr.nx * n,
    y,
    a[1] + fr.uz * u + fr.nz * n,
  ];
  const { u0, u1, y0, topFlat } = piece;
  const topPts: TopProfilePoint[] = topFlat != null ? [{ u: u0, h: topFlat }, { u: u1, h: topFlat }] : clipProfile(top, u0, u1);

  const pos: number[] = [];
  const norm: number[] = [];
  const uv: number[] = [];
  const tw = opts.tw, th = opts.th;

  // --- inner face (+n): strip between bottom y0 and the top polyline
  // UVs are world-tiled: u along the wall / tw, y / th.
  const innerStart = pos.length / 3;
  for (let i = 0; i < topPts.length - 1; i++) {
    const ua = topPts[i].u, ub = topPts[i + 1].u;
    const ha = topPts[i].h, hb = topPts[i + 1].h;
    const pa = P(ua, y0, +n2);
    const pb = P(ub, y0, +n2);
    const pc = P(ub, hb, +n2);
    const pd = P(ua, ha, +n2);
    const nrm: [number, number, number] = [fr.nx, 0, fr.nz];
    pos.push(...pa, ...pb, ...pc);
    norm.push(...nrm, ...nrm, ...nrm);
    if (tw && th) uv.push(ua / tw, y0 / th, ub / tw, y0 / th, ub / tw, hb / th);
    else uv.push(0, 0, 0, 0, 0, 0);
    pos.push(...pa, ...pc, ...pd);
    norm.push(...nrm, ...nrm, ...nrm);
    if (tw && th) uv.push(ua / tw, y0 / th, ub / tw, hb / th, ua / tw, ha / th);
    else uv.push(0, 0, 0, 0, 0, 0);
  }
  const innerCount = pos.length / 3 - innerStart;

  // --- outer face (-n)
  for (let i = 0; i < topPts.length - 1; i++) {
    const pa = P(topPts[i].u, topPts[i].h, -n2);
    const pb = P(topPts[i + 1].u, topPts[i + 1].h, -n2);
    const pc = P(topPts[i + 1].u, y0, -n2);
    const pd = P(topPts[i].u, y0, -n2);
    const nrm: [number, number, number] = [-fr.nx, 0, -fr.nz];
    pos.push(...pa, ...pb, ...pc, ...pa, ...pc, ...pd);
    for (let j = 0; j < 6; j++) norm.push(...nrm);
    for (let j = 0; j < 6; j++) uv.push(0, 0);
  }

  // --- bottom face (y = y0)
  {
    const pa = P(u0, y0, -n2), pb = P(u1, y0, -n2), pc = P(u1, y0, +n2), pd = P(u0, y0, +n2);
    const nrm: [number, number, number] = [0, -1, 0];
    pos.push(...pa, ...pb, ...pc, ...pa, ...pc, ...pd);
    for (let j = 0; j < 6; j++) norm.push(...nrm);
    for (let j = 0; j < 6; j++) uv.push(0, 0);
  }

  // --- top face(s): between consecutive top points, thin quad
  for (let i = 0; i < topPts.length - 1; i++) {
    const pa = P(topPts[i].u, topPts[i].h, -n2);
    const pb = P(topPts[i + 1].u, topPts[i + 1].h, -n2);
    const pc = P(topPts[i + 1].u, topPts[i + 1].h, +n2);
    const pd = P(topPts[i].u, topPts[i].h, +n2);
    const ex = pb[0] - pa[0], ez = pb[2] - pa[2];
    const len = Math.hypot(ex, ez) || 1;
    const nrm: [number, number, number] = [-ez / len, 0, ex / len]; // perpendicular to wall direction, pointing +n
    pos.push(...pa, ...pb, ...pc, ...pa, ...pc, ...pd);
    for (let j = 0; j < 6; j++) norm.push(...nrm);
    for (let j = 0; j < 6; j++) uv.push(0, 0);
  }

  // --- end caps at u0 and u1
  const cap = (u: number, dir: number) => {
    const h = topHeightAt(topPts, u);
    const pa = P(u, y0, -n2), pb = P(u, y0, +n2), pc = P(u, h, +n2), pd = P(u, h, -n2);
    const nrm: [number, number, number] = [fr.ux * dir, 0, fr.uz * dir];
    pos.push(...pa, ...pb, ...pc, ...pa, ...pc, ...pd);
    for (let j = 0; j < 6; j++) norm.push(...nrm);
    for (let j = 0; j < 6; j++) uv.push(0, 0);
  };
  cap(u0, -1);
  cap(u1, +1);

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(norm, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  if (innerCount > 0) {
    geo.addGroup(0, innerCount * 3, 0);
    geo.addGroup(innerCount * 3, (pos.length / 3 - innerCount) * 3, 1);
  }
  return geo;
}

/** Convenience builder: assemble the full set of meshes for a shaped (non-rectangle) wall. */
export function shapedWallMeshes(spec: WallSpec): { geo: THREE.BufferGeometry; position: [number, number, number]; name: string }[] {
  const a = spec.outline[0];
  const b = spec.outline[spec.outline.length - 1];
  const fr = wallFrame(a, b);
  const h = spec.height;

  const out: { geo: THREE.BufferGeometry; position: [number, number, number]; name: string }[] = [];

  if (spec.profile === 'gable') {
    // top slope: height at end a, height + slopeRise at end b
    out.push({ geo: prismGeometry(a, b, spec.thickness, h, h + (spec.slopeRise || 0)), position: [0, 0, 0], name: 'gable' });
  } else if (spec.profile === 'stairs') {
    // stepped descending top: N steps from full height down to ~40% height
    const steps = Math.max(2, spec.stairSteps || 5);
    for (let i = 0; i < steps; i++) {
      const frac0 = 1 - (i / steps) * 0.6;
      const frac1 = 1 - ((i + 1) / steps) * 0.6;
      const hTop = Math.max(0, h * frac0);
      const hBot = Math.max(0, h * frac1);
      const u0 = (fr.len / steps) * i;
      const u1 = (fr.len / steps) * (i + 1);
      const p0: [number, number] = [a[0] + fr.ux * u0, a[1] + fr.uz * u0];
      const p1: [number, number] = [a[0] + fr.ux * u1, a[1] + fr.uz * u1];
      out.push({ geo: stepGeometry(p0, p1, spec.thickness, Math.min(hTop, hBot), Math.max(hTop, hBot)), position: [0, 0, 0], name: `step${i}` });
    }
  } else {
    // rectangle (fallback)
    out.push({ geo: prismGeometry(a, b, spec.thickness, h, h), position: [0, 0, 0], name: 'rect' });
  }

  if (spec.profile === 'boxing') {
    // bulkhead: a box protruding from the wall face into the room
    const len = fr.len || 1;
    const from = spec.boxFrom ?? 0;
    const bl = Math.max(0, Math.min(spec.boxLength ?? len, len - from));
    out.push({
      geo: orientedBoxGeometry(fr, a, from, bl, spec.boxDepth || 120, spec.thickness, spec.boxTop || 450),
      position: [0, 0, 0],
      name: 'boxing',
    });
  }

  return out;
}

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

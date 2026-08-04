import { create } from 'zustand';
import type { DesignData, PlacedItem, RoomState, TextureAssignment, WallOpening, WallSpec } from '../lib/types';
import { buildWalls, polygonCentroid } from '../lib/geometry';
import { useEditorStore } from './editor-store';

export const DEFAULT_CEILING = 2400;
export const DEFAULT_WALL_THICKNESS = 100;
/** Freehand-drawn rooms default to 3 m tall walls (basic rectangles). */
export const DRAWN_WALL_HEIGHT = 3000;

/** Auto-generate one rectangular wall per floor edge. */
export function wallsFromFloor(
  floorPoints: [number, number][],
  ceilingHeight: number,
  thickness: number,
  wallHeight = ceilingHeight,
): WallSpec[] {
  const n = floorPoints.length;
  const walls: WallSpec[] = [];
  for (let i = 0; i < n; i++) {
    const a = floorPoints[i];
    const b = floorPoints[(i + 1) % n];
    if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 1) continue;
    walls.push({
      id: crypto.randomUUID(),
      outline: [a, b],
      thickness,
      height: wallHeight,
      profile: 'rectangle',
      slopeRise: 0,
      stairSteps: 6,
      boxLength: Math.round((b[0] - a[0] || b[1] - a[1]) / 2),
      boxDepth: 120,
      boxFrom: 150,
      boxTop: 450,
      cornerA: i,
      cornerB: (i + 1) % n,
      topPoints: [],
    });
  }
  return walls;
}

/** Top height (mm) at each floor corner; falls back to the ceiling height. */
export function cornerHeightsFor(room: RoomState): number[] {
  if (room.cornerHeights && room.cornerHeights.length === room.floorPoints.length) return room.cornerHeights;
  return room.floorPoints.map(() => room.ceilingHeight);
}

/** A fresh plain rectangle wall (used when a wall appears without an old spec). */
function freshWall(a: [number, number], b: [number, number], thickness: number, height: number, cornerA: number, cornerB: number): WallSpec {
  return {
    id: crypto.randomUUID(),
    outline: [a, b],
    thickness,
    height,
    profile: 'rectangle',
    slopeRise: 0,
    stairSteps: 6,
    boxLength: Math.round((b[0] - a[0] || b[1] - a[1]) / 2),
    boxDepth: 120,
    boxFrom: 150,
    boxTop: 450,
    cornerA,
    cornerB,
    topPoints: [],
  };
}

/**
 * Rebuild every wall's outline from the current floor polygon, preserving each
 * wall's shape/profile by index. Used after a corner is moved or inserted.
 */
function syncWallsFromFloor(room: RoomState): WallSpec[] {
  const n = room.floorPoints.length;
  const ch = cornerHeightsFor(room);
  const walls: WallSpec[] = [];
  for (let i = 0; i < n; i++) {
    const a = room.floorPoints[i];
    const b = room.floorPoints[(i + 1) % n];
    if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 1) continue;
    const old = room.walls[i];
    if (old) {
      const ca = old.cornerA ?? i;
      const cb = old.cornerB ?? (i + 1) % n;
      const rect = old.profile === 'rectangle';
      walls.push({
        ...old,
        outline: [a, b],
        cornerA: ca,
        cornerB: cb,
        topPoints: old.topPoints ?? [],
        // rectangle walls track their end corner heights
        height: rect ? Math.max(ch[ca] ?? 0, ch[cb] ?? 0) : old.height,
      });
    } else {
      walls.push(freshWall(a, b, room.wallThickness, ch[i] ?? room.ceilingHeight, i, (i + 1) % n));
    }
  }
  return walls;
}

/** Pre-drag snapshot for live edits (corner / top-point drags). */
let pendingSnapshot: DesignData | null = null;

const RECT = (w: number, d: number): [number, number][] => [
  [-w / 2, -d / 2],
  [w / 2, -d / 2],
  [w / 2, d / 2],
  [-w / 2, d / 2],
];

function makeRoom(pts: [number, number][], ceiling: number, thickness: number): RoomState {
  return {
    floorPoints: pts,
    walls: wallsFromFloor(pts, ceiling, thickness),
    ceilingHeight: ceiling,
    wallThickness: thickness,
    closed: true,
    cornerHeights: pts.map(() => ceiling),
  };
}

export function defaultRoom(closed = true): RoomState {
  // Standard small UK bathroom: 2400 x 1800, centered on origin
  return makeRoom(RECT(2400, 1800), DEFAULT_CEILING, DEFAULT_WALL_THICKNESS);
}

export function emptyDesign(): DesignData {
  return {
    room: defaultRoom(),
    doors: [],
    windows: [],
    items: [],
    floorTexture: null,
    wallTextures: {},
    ceilingTexture: null,
    version: 1,
  };
}

/** Quick-start room templates (competitor feature). Returns a closed rectangular room. */
export const ROOM_TEMPLATES: { name: string; w: number; d: number; ceiling: number }[] = [
  { name: 'Small UK Bathroom', w: 2400, d: 1800, ceiling: 2400 },
  { name: 'Family Bathroom', w: 3000, d: 2500, ceiling: 2400 },
  { name: 'Large Master', w: 3600, d: 3000, ceiling: 2600 },
  { name: 'En-suite (L-shape)', w: 2400, d: 2000, ceiling: 2400 },
];

export function templateRoom(w: number, d: number, ceiling: number): RoomState {
  return makeRoom(RECT(w, d), ceiling, DEFAULT_WALL_THICKNESS);
}

interface DesignStore {
  design: DesignData;
  selectedItemId: string | null;
  selectedSurface: { type: 'floor' | 'ceiling' | 'wall'; index: number } | null;
  designId: number | null;
  designName: string;
  savedAt: string | null;
  collisionMap: Record<string, boolean>;

  // undo/redo
  past: DesignData[];
  future: DesignData[];
  canUndo: boolean;
  canRedo: boolean;

  loadDesign: (d: DesignData, name?: string) => void;
  resetDesign: () => void;

  // room
  setRoom: (room: RoomState) => void;
  startDrawing: () => void;
  addWallPoint: (x: number, z: number) => void;
  closePolygon: () => void;
  undoPoint: () => void;
  setCeilingHeight: (h: number) => void;
  setWallThickness: (t: number) => void;
  updateWall: (id: string, patch: Partial<WallSpec>) => void;

  // room shape editing (2D plan): drag corners / split walls
  /** Snapshot current design once before a live drag (corner or wall top). */
  beginEdit: () => void;
  /** Push the pre-drag snapshot onto the undo stack (call on pointer-up). */
  commitEdit: () => void;
  /** Discard a pending pre-drag snapshot without pushing it. */
  cancelEdit: () => void;
  /** Live-update one floor corner during a drag (no undo snapshot). */
  moveCorner: (index: number, x: number, z: number) => void;
  /** Set a wall's length exactly; its far corner moves along the wall's own
   *  direction, so the adjacent walls stay connected. */
  setWallLength: (wallIndex: number, length: number) => void;
  /** Delete a floor corner (min 3 corners kept); merges the two adjacent walls. */
  removeCorner: (index: number) => void;
  /** Split a wall at a point: inserts a new floor corner + wall (atomic). */
  addCornerOnWall: (wallIndex: number, x: number, z: number) => void;
  /** Live-update the shared height of one floor corner (affects both adjacent walls). */
  setCornerHeight: (index: number, h: number) => void;
  /** Live-update one intermediate top point of a wall (position along wall + height). */
  moveTopPoint: (wallId: string, pointIndex: number, u: number, h: number) => void;
  /** Insert a new point on a wall's top edge (atomic). */
  addTopPoint: (wallId: string, u: number, h: number) => void;
  /** Delete an intermediate top point (atomic). */
  removeTopPoint: (wallId: string, pointIndex: number) => void;
  /** Set both end heights of a wall (uniform). */
  setWallHeights: (wallId: string, hA: number, hB: number) => void;

  // openings
  addOpening: (o: WallOpening) => void;
  removeOpening: (id: string) => void;
  /** Clear all doors/windows/items — used when importing a replacement plan/room. */
  clearRoomContents: () => void;

  // items
  addItem: (item: PlacedItem) => void;
  updateItem: (id: string, patch: Partial<PlacedItem>) => void;
  moveItem: (id: string, position: [number, number, number]) => void;
  rotateItem: (id: string, rotation: number) => void;
  removeItem: (id: string) => void;
  selectItem: (id: string | null) => void;

  // surfaces
  selectSurface: (s: { type: 'floor' | 'ceiling' | 'wall'; index: number } | null) => void;
  setFloorTexture: (t: TextureAssignment | null) => void;
  setWallTexture: (index: number, t: TextureAssignment | null) => void;
  setCeilingTexture: (t: TextureAssignment | null) => void;
  applyToAllWalls: (t: TextureAssignment) => void;

  // save/load
  setDesignId: (id: number | null) => void;
  setDesignName: (name: string) => void;
  setSavedAt: (at: string) => void;
  setCollisionMap: (m: Record<string, boolean>) => void;

  undo: () => void;
  redo: () => void;
}

function snapshot(d: DesignData): DesignData {
  return JSON.parse(JSON.stringify(d));
}

export const useDesignStore = create<DesignStore>()((set, get) => ({
  design: emptyDesign(),
  selectedItemId: null,
  selectedSurface: null,
  designId: null,
  designName: 'Untitled Design',
  savedAt: null,
  collisionMap: {},
  past: [],
  future: [],
  canUndo: false,
  canRedo: false,

  loadDesign: (d, name) => {
    const data = snapshot(d);
    // older saved designs may lack per-wall shapes — regenerate from the floor
    const room = data.room;
    if (room && room.closed && room.floorPoints?.length >= 3 && (!room.walls || room.walls.length === 0)) {
      room.walls = wallsFromFloor(room.floorPoints, room.ceilingHeight, room.wallThickness);
    }
    // backfill shared corner heights + per-wall corner indices for legacy data
    if (room && room.closed) {
      const n = room.floorPoints.length;
      if (!room.cornerHeights || room.cornerHeights.length !== n) {
        room.cornerHeights = room.floorPoints.map((_, i) => {
          const hPrev = room.walls?.[(i - 1 + n) % n]?.height ?? 0;
          const hNext = room.walls?.[i]?.height ?? 0;
          return Math.max(hPrev, hNext, 1);
        });
      }
      room.walls = (room.walls ?? []).map((w, i) => ({
        ...w,
        cornerA: w.cornerA ?? i,
        cornerB: w.cornerB ?? (i + 1) % n,
        topPoints: w.topPoints ?? [],
      }));
    }
    return set({
      design: data,
      designName: name ?? get().designName,
      selectedItemId: null,
      selectedSurface: null,
      past: [],
      future: [],
      canUndo: false,
      canRedo: false,
    });
  },

  resetDesign: () =>
    set({
      design: emptyDesign(),
      selectedItemId: null,
      selectedSurface: null,
      designId: null,
      designName: 'Untitled Design',
      savedAt: null,
      past: [],
      future: [],
      canUndo: false,
      canRedo: false,
    }),

  setRoom: (room) => {
    const prev = snapshot(get().design);
    set((s) => ({
      design: { ...s.design, room },
      past: [...s.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  startDrawing: () => {
    const s = get();
    if (!s.design.room.closed) return; // already drawing
    const prev = snapshot(s.design);
    set((st) => ({
      design: {
        ...st.design,
        room: { ...st.design.room, floorPoints: [], walls: [], cornerHeights: [], closed: false },
      },
      past: [...st.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  addWallPoint: (x, z) => {
    const s = get();
    const pts = [...s.design.room.floorPoints, [x, z] as [number, number]];
    // drop if duplicate of last point
    const last = pts[pts.length - 2];
    if (last && Math.hypot(last[0] - x, last[1] - z) < 5) return;
    set({ design: { ...s.design, room: { ...s.design.room, floorPoints: pts } } });
  },

  closePolygon: () => {
    const s = get();
    const pts = s.design.room.floorPoints;
    if (pts.length < 3) return;
    // remove trailing point if it's within snap range of the first
    let cleaned = pts;
    const first = pts[0];
    const last = pts[pts.length - 1];
    if (Math.hypot(first[0] - last[0], first[1] - last[1]) < 100) {
      cleaned = pts.slice(0, -1);
    }
    if (cleaned.length < 3) return;
    const prev = snapshot(s.design);
    const room = { ...s.design.room };
    // drawn rooms default to 3 m tall walls; ceiling follows so the slab is coherent
    const H = DRAWN_WALL_HEIGHT;
    set((st) => ({
      design: {
        ...st.design,
        room: {
          ...room,
          floorPoints: cleaned,
          walls: wallsFromFloor(cleaned, H, room.wallThickness, H),
          cornerHeights: cleaned.map(() => H),
          ceilingHeight: H,
          closed: true,
        },
      },
      past: [...st.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  undoPoint: () => {
    const s = get();
    if (s.design.room.closed) return;
    const pts = s.design.room.floorPoints.slice(0, -1);
    if (pts.length < 1) return;
    set({ design: { ...s.design, room: { ...s.design.room, floorPoints: pts } } });
  },

  setCeilingHeight: (h) => {
    // "Ceiling max height": caps everything. Wall/corner values ABOVE the new
    // value are pulled down to it; values already below it stay unchanged.
    const s = get();
    const room = s.design.room;
    const ch = room.cornerHeights;
    const nextCh = ch && ch.length > 0 ? ch.map((v) => Math.min(v, h)) : ch;
    const walls = room.walls.map((w) => {
      if (w.profile !== 'rectangle') return w;
      if (nextCh) {
        const ca = w.cornerA ?? 0;
        const cb = w.cornerB ?? 0;
        return { ...w, cornerA: ca, cornerB: cb, height: Math.max(nextCh[ca] ?? 0, nextCh[cb] ?? 0) };
      }
      return w.height > h ? { ...w, height: h } : w;
    });
    get().setRoom({ ...room, ceilingHeight: h, cornerHeights: nextCh, walls });
  },

  setWallThickness: (t) =>
    get().setRoom({
      ...get().design.room,
      wallThickness: t,
      walls: get().design.room.walls.map((w) => ({ ...w, thickness: t })),
    }),

  updateWall: (id, patch) => {
    const prev = snapshot(get().design);
    set((s) => ({
      design: {
        ...s.design,
        room: {
          ...s.design.room,
          walls: s.design.room.walls.map((w) => (w.id === id ? { ...w, ...patch } : w)),
        },
      },
      past: [...s.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  beginEdit: () => {
    pendingSnapshot = snapshot(get().design);
  },

  commitEdit: () => {
    if (!pendingSnapshot) return;
    const prev = pendingSnapshot;
    pendingSnapshot = null;
    // skip no-op edits (a press-release that never moved) so undo isn't polluted
    if (JSON.stringify(prev) === JSON.stringify(get().design)) return;
    set((s) => ({
      past: [...s.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  cancelEdit: () => {
    pendingSnapshot = null;
  },

  moveCorner: (index, x, z) => {
    const s = get();
    const room = s.design.room;
    if (!room.floorPoints[index]) return;
    const floorPoints = room.floorPoints.map((p, i) => (i === index ? [x, z] : p)) as [number, number][];
    set({
      design: { ...s.design, room: { ...room, floorPoints, walls: syncWallsFromFloor({ ...room, floorPoints }) } },
    });
  },

  setWallLength: (wallIndex, length) => {
    const s = get();
    const room = s.design.room;
    const n = room.floorPoints.length;
    if (!room.closed || n < 3 || wallIndex < 0 || wallIndex >= n) return;
    const target = Math.max(100, Math.min(50000, Math.round(length / 5) * 5));
    const a = room.floorPoints[wallIndex];
    const bIdx = (wallIndex + 1) % n;
    const b = room.floorPoints[bIdx];
    const dx = b[0] - a[0], dz = b[1] - a[1];
    const len = Math.hypot(dx, dz);
    if (len < 1 || Math.abs(len - target) < 1) return;
    // move the wall's far corner along the wall's own direction — the adjacent
    // walls share that corner, so they follow and the polygon stays connected
    const nb: [number, number] = [a[0] + (dx / len) * target, a[1] + (dz / len) * target];
    const floorPoints = room.floorPoints.map((p, i) => (i === bIdx ? nb : p)) as [number, number][];
    const walls = syncWallsFromFloor({ ...room, floorPoints }).map((w, i) => {
      if (i !== wallIndex) return w;
      // keep this wall's intermediate top points inside the new length
      const topPoints = (w.topPoints ?? [])
        .filter((p) => p.u < target - 5)
        .map((p) => ({ u: Math.max(5, Math.min(target - 5, p.u)), h: p.h }));
      return { ...w, topPoints };
    });
    // openings on this wall that would sit past the new end get pulled back in
    const clampPos = (o: WallOpening): WallOpening =>
      o.wallIndex === wallIndex ? { ...o, pos: Math.max(50, Math.min(target - 50, o.pos)) } : o;
    const prev = snapshot(s.design);
    set((st) => ({
      design: {
        ...st.design,
        room: { ...room, floorPoints, walls },
        doors: st.design.doors.map(clampPos),
        windows: st.design.windows.map(clampPos),
      },
      past: [...st.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  removeCorner: (index) => {
    const s = get();
    const room = s.design.room;
    const n = room.floorPoints.length;
    if (!room.closed || n <= 3 || index < 0 || index >= n) return; // a room keeps at least 3 corners
    const m = n - 1;
    const prevIdx = (index - 1 + n) % n;
    const floorPoints = room.floorPoints.filter((_, i) => i !== index);
    const ch = cornerHeightsFor(room).filter((_, i) => i !== index);
    const prevWall = room.walls[prevIdx];
    const delWall = room.walls[index];
    const prevLen = prevWall
      ? Math.hypot(
          prevWall.outline[prevWall.outline.length - 1][0] - prevWall.outline[0][0],
          prevWall.outline[prevWall.outline.length - 1][1] - prevWall.outline[0][1],
        )
      : 0;
    const newOf = (k: number) => (k < index ? k : k - 1);
    const mergedNewIdx = newOf(prevIdx);
    const walls: WallSpec[] = [];
    for (let k = 0; k < n; k++) {
      if (k === index) continue; // this wall merges into the previous one
      const old = room.walls[k];
      const ca = newOf(k);
      const cb = (ca + 1) % m;
      const wa = floorPoints[ca];
      const wb = floorPoints[cb];
      if (k === prevIdx) {
        // merged wall = previous wall extended by the deleted wall's segment
        const topPoints = [
          ...(prevWall?.topPoints ?? []),
          ...(delWall?.topPoints ?? []).map((p) => ({ u: p.u + prevLen, h: p.h })),
        ].sort((p, q) => p.u - q.u);
        walls.push(
          old
            ? { ...old, outline: [wa, wb], cornerA: ca, cornerB: cb, topPoints, height: Math.max(ch[ca] ?? 0, ch[cb] ?? 0) }
            : freshWall(wa, wb, room.wallThickness, ch[ca] ?? room.ceilingHeight, ca, cb),
        );
      } else {
        walls.push(
          old
            ? { ...old, outline: [wa, wb], cornerA: ca, cornerB: cb, topPoints: old.topPoints ?? [] }
            : freshWall(wa, wb, room.wallThickness, ch[ca] ?? room.ceilingHeight, ca, cb),
        );
      }
    }
    // openings: those on the deleted wall move onto the merged wall; the rest shift
    const remap = (o: WallOpening): WallOpening =>
      o.wallIndex === index ? { ...o, wallIndex: mergedNewIdx, pos: prevLen + o.pos } : { ...o, wallIndex: newOf(o.wallIndex) };
    const prev = snapshot(s.design);
    set((st) => ({
      design: {
        ...st.design,
        room: { ...room, floorPoints, cornerHeights: ch, walls },
        doors: st.design.doors.map(remap),
        windows: st.design.windows.map(remap),
      },
      selectedSurface: null,
      past: [...st.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
    // the selected wall may have been merged away
    const ed = useEditorStore.getState();
    if (ed.selectedWallId) {
      const still = get().design.room.walls.some((w) => w.id === ed.selectedWallId);
      if (!still) ed.setSelectedWall(null);
    }
  },

  addCornerOnWall: (wallIndex, x, z) => {
    const s = get();
    const room = s.design.room;
    const n = room.floorPoints.length;
    if (!room.closed || n < 3) return;
    const a = room.floorPoints[wallIndex % n];
    const b = room.floorPoints[(wallIndex + 1) % n];
    const dx = b[0] - a[0], dz = b[1] - a[1];
    const len = Math.hypot(dx, dz);
    if (len < 50) return;
    let t = ((x - a[0]) * dx + (z - a[1]) * dz) / (len * len);
    t = Math.max(0.05, Math.min(0.95, t));
    const px = Math.round(((a[0] + t * dx) / 25)) * 25;
    const pz = Math.round(((a[1] + t * dz) / 25)) * 25;
    // recompute t from the snapped point
    const snapDx = px - a[0], snapDz = pz - a[1];
    const t2 = Math.max(0.05, Math.min(0.95, (snapDx * dx + snapDz * dz) / (len * len)));
    const insertAt = wallIndex + 1;
    const floorPoints: [number, number][] = [];
    for (let i = 0; i <= n; i++) {
      if (i < insertAt) floorPoints.push(room.floorPoints[i]);
      else if (i === insertAt) floorPoints.push([px, pz]);
      else floorPoints.push(room.floorPoints[i - 1]);
    }
    const ch = cornerHeightsFor(room);
    const hNew = ch[wallIndex] + (ch[(wallIndex + 1) % n] - ch[wallIndex]) * t2;
    const cornerHeights = [...ch.slice(0, insertAt), hNew, ...ch.slice(insertAt)];

    // rebuild walls, splitting wall `wallIndex` at the new corner
    const oldLen = len;
    const walls: WallSpec[] = [];
    for (let j = 0; j <= n; j++) {
      const ca = j;
      const cb = (j + 1) % (n + 1);
      const wa = floorPoints[ca];
      const wb = floorPoints[cb];
      if (Math.hypot(wb[0] - wa[0], wb[1] - wa[1]) < 1) continue;
      if (j < wallIndex) {
        const old = room.walls[j];
        walls.push(old ? { ...old, outline: [wa, wb], cornerA: ca, cornerB: cb, topPoints: old.topPoints ?? [] } : freshWall(wa, wb, room.wallThickness, cornerHeights[ca], ca, cb));
      } else if (j === wallIndex) {
        const old = room.walls[wallIndex];
        const cut = t2 * oldLen;
        const mids = (old?.topPoints ?? []).filter((p) => p.u <= cut).map((p) => ({ u: p.u, h: p.h }));
        walls.push(
          old
            ? { ...old, outline: [wa, wb], cornerA: ca, cornerB: cb, topPoints: mids, height: Math.max(cornerHeights[ca], cornerHeights[cb]) }
            : freshWall(wa, wb, room.wallThickness, cornerHeights[ca], ca, cb),
        );
      } else {
        // j === wallIndex + 1: the new second half; j > that: shifted old walls
        const old = room.walls[j - 1];
        if (j === wallIndex + 1) {
          const cut = t2 * oldLen;
          const mids = (old?.topPoints ?? [])
            .filter((p) => p.u > cut)
            .map((p) => ({ u: Math.max(1, p.u - cut), h: p.h }));
          walls.push(
            old
              ? { ...old, outline: [wa, wb], cornerA: ca, cornerB: cb, profile: 'rectangle', slopeRise: 0, topPoints: mids, height: Math.max(cornerHeights[ca], cornerHeights[cb]) }
              : freshWall(wa, wb, room.wallThickness, cornerHeights[ca], ca, cb),
          );
        } else {
          walls.push(old ? { ...old, outline: [wa, wb], cornerA: ca, cornerB: cb, topPoints: old.topPoints ?? [] } : freshWall(wa, wb, room.wallThickness, cornerHeights[ca], ca, cb));
        }
      }
    }

    // openings: those on the split wall move to the right half if past the cut;
    // every opening after the split wall shifts one wall index
    const doors = s.design.doors.map((o) => {
      if (o.wallIndex < wallIndex) return o;
      if (o.wallIndex === wallIndex) {
        if (o.pos <= t2 * oldLen) return { ...o, pos: Math.max(50, Math.min(t2 * oldLen - 50, o.pos)) };
        return { ...o, wallIndex: wallIndex + 1, pos: Math.max(50, o.pos - t2 * oldLen) };
      }
      return { ...o, wallIndex: o.wallIndex + 1 };
    });
    const windows = s.design.windows.map((o) => {
      if (o.wallIndex < wallIndex) return o;
      if (o.wallIndex === wallIndex) {
        if (o.pos <= t2 * oldLen) return { ...o, pos: Math.max(50, Math.min(t2 * oldLen - 50, o.pos)) };
        return { ...o, wallIndex: wallIndex + 1, pos: Math.max(50, o.pos - t2 * oldLen) };
      }
      return { ...o, wallIndex: o.wallIndex + 1 };
    });

    const prev = snapshot(s.design);
    set((st) => ({
      design: {
        ...st.design,
        room: { ...room, floorPoints, cornerHeights, walls },
        doors,
        windows,
      },
      past: [...st.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  setCornerHeight: (index, h) => {
    const s = get();
    const room = s.design.room;
    const n = room.floorPoints.length;
    if (!room.cornerHeights || index >= n) return;
    const ch = [...room.cornerHeights];
    ch[index] = h;
    const walls = room.walls.map((w, idx) => {
      const ca = w.cornerA ?? idx;
      const cb = w.cornerB ?? (idx + 1) % n;
      if (ca !== index && cb !== index) return w;
      const patch: Partial<WallSpec> = {};
      if (w.profile === 'gable') {
        patch.profile = 'rectangle';
        patch.slopeRise = 0;
      }
      patch.height = Math.max(ch[ca] ?? 0, ch[cb] ?? 0);
      return { ...w, ...patch };
    });
    set({ design: { ...s.design, room: { ...room, cornerHeights: ch, walls } } });
  },

  moveTopPoint: (wallId, pointIndex, u, h) => {
    const s = get();
    const room = s.design.room;
    const wall = room.walls.find((w) => w.id === wallId);
    if (!wall) return;
    const a = wall.outline[0];
    const b = wall.outline[wall.outline.length - 1];
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const cu = Math.max(5, Math.min(L - 5, Math.round(u / 5) * 5));
    const ch = Math.max(50, Math.min(6000, Math.round(h / 5) * 5));
    const walls = room.walls.map((w) => {
      if (w.id !== wallId) return w;
      const topPoints = (w.topPoints ?? [])
        .map((p, i) => (i === pointIndex ? { u: cu, h: ch } : p))
        .sort((p, q) => p.u - q.u); // keep sorted by u so indices stay in sync with the rendered profile
      const patch: Partial<WallSpec> = { topPoints };
      if (w.profile === 'gable') {
        patch.profile = 'rectangle';
        patch.slopeRise = 0;
      }
      return { ...w, ...patch };
    });
    set({ design: { ...s.design, room: { ...room, walls } } });
  },

  addTopPoint: (wallId, u, h) => {
    const s = get();
    const room = s.design.room;
    const wall = room.walls.find((w) => w.id === wallId);
    if (!wall) return;
    const a = wall.outline[0];
    const b = wall.outline[wall.outline.length - 1];
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const cu = Math.max(5, Math.min(L - 5, Math.round(u / 5) * 5));
    const cuh = Math.round(h / 25) * 25;
    const topPoints = [...(wall.topPoints ?? [])];
    if (topPoints.some((p) => Math.abs(p.u - cu) < 50)) return; // already have a point here
    topPoints.push({ u: cu, h: cuh });
    topPoints.sort((p, q) => p.u - q.u);
    const patch: Partial<WallSpec> = { topPoints };
    if (wall.profile === 'gable') {
      patch.profile = 'rectangle';
      patch.slopeRise = 0;
    }
    const prev = snapshot(s.design);
    set((st) => ({
      design: {
        ...st.design,
        room: {
          ...room,
          walls: room.walls.map((w) => (w.id === wallId ? { ...w, ...patch } : w)),
        },
      },
      past: [...st.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  removeTopPoint: (wallId, pointIndex) => {
    const s = get();
    const room = s.design.room;
    const wall = room.walls.find((w) => w.id === wallId);
    if (!wall) return;
    const topPoints = (wall.topPoints ?? []).filter((_, i) => i !== pointIndex);
    const prev = snapshot(s.design);
    set((st) => ({
      design: {
        ...st.design,
        room: {
          ...room,
          walls: room.walls.map((w) => (w.id === wallId ? { ...w, topPoints } : w)),
        },
      },
      past: [...st.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  setWallHeights: (wallId, hA, hB) => {
    const s = get();
    const room = s.design.room;
    const wall = room.walls.find((w) => w.id === wallId);
    if (!wall) return;
    const ca = wall.cornerA ?? room.walls.indexOf(wall);
    const cb = wall.cornerB ?? (ca + 1) % room.floorPoints.length;
    const ch = [...cornerHeightsFor(room)];
    ch[ca] = Math.round(hA);
    ch[cb] = Math.round(hB);
    const walls = room.walls.map((w) => {
      const wa = w.cornerA ?? 0;
      const wb = w.cornerB ?? 0;
      return { ...w, height: Math.max(ch[wa] ?? 0, ch[wb] ?? 0) };
    });
    get().setRoom({ ...room, cornerHeights: ch, walls });
  },

  addOpening: (o) => {
    const prev = snapshot(get().design);
    set((s) => {
      const isDoor = o.type === 'door';
      const list = isDoor ? [...s.design.doors, o] : [...s.design.windows, o];
      return {
        design: { ...s.design, doors: isDoor ? list : s.design.doors, windows: isDoor ? s.design.windows : list },
        past: [...s.past.slice(-49), prev],
        future: [],
        canUndo: true,
        canRedo: false,
      };
    });
  },

  removeOpening: (id) => {
    const prev = snapshot(get().design);
    set((s) => ({
      design: {
        ...s.design,
        doors: s.design.doors.filter((d) => d.id !== id),
        windows: s.design.windows.filter((w) => w.id !== id),
      },
      past: [...s.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  clearRoomContents: () => {
    const prev = snapshot(get().design);
    set((s) => ({
      design: { ...s.design, doors: [], windows: [], items: [] },
      selectedItemId: null,
      past: [...s.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  addItem: (item) => {
    const prev = snapshot(get().design);
    set((s) => ({
      design: { ...s.design, items: [...s.design.items, item] },
      selectedItemId: item.id,
      past: [...s.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  updateItem: (id, patch) => {
    set((s) => ({
      design: {
        ...s.design,
        items: s.design.items.map((it) => (it.id === id ? { ...it, ...patch } : it)),
      },
    }));
  },

  moveItem: (id, position) => get().updateItem(id, { position }),

  rotateItem: (id, rotation) => {
    const prev = snapshot(get().design);
    set((s) => ({
      design: {
        ...s.design,
        items: s.design.items.map((it) => (it.id === id ? { ...it, rotation } : it)),
      },
      past: [...s.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  removeItem: (id) => {
    const prev = snapshot(get().design);
    set((s) => ({
      design: { ...s.design, items: s.design.items.filter((it) => it.id !== id) },
      selectedItemId: s.selectedItemId === id ? null : s.selectedItemId,
      past: [...s.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  selectItem: (id) => set({ selectedItemId: id }),

  selectSurface: (sel) => set({ selectedSurface: sel }),

  setFloorTexture: (t) => {
    const prev = snapshot(get().design);
    set((s) => ({
      design: { ...s.design, floorTexture: t },
      past: [...s.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  setWallTexture: (index, t) => {
    const prev = snapshot(get().design);
    set((s) => {
      const wallTextures = { ...s.design.wallTextures };
      if (t) wallTextures[index] = t;
      else delete wallTextures[index];
      return {
        design: { ...s.design, wallTextures },
        past: [...s.past.slice(-49), prev],
        future: [],
        canUndo: true,
        canRedo: false,
      };
    });
  },

  setCeilingTexture: (t) => {
    const prev = snapshot(get().design);
    set((s) => ({
      design: { ...s.design, ceilingTexture: t },
      past: [...s.past.slice(-49), prev],
      future: [],
      canUndo: true,
      canRedo: false,
    }));
  },

  applyToAllWalls: (t) => {
    const prev = snapshot(get().design);
    set((s) => {
      const walls = buildWalls(s.design.room.floorPoints);
      const wallTextures: Record<number, TextureAssignment> = {};
      walls.forEach((w) => (wallTextures[w.index] = t));
      return {
        design: { ...s.design, wallTextures },
        past: [...s.past.slice(-49), prev],
        future: [],
        canUndo: true,
        canRedo: false,
      };
    });
  },

  setDesignId: (id) => set({ designId: id }),
  setDesignName: (name) => set({ designName: name }),
  setSavedAt: (at) => set({ savedAt: at }),

  setCollisionMap: (m) => set({ collisionMap: m }),

  undo: () => {
    const s = get();
    if (s.past.length === 0) return;
    const prev = s.past[s.past.length - 1];
    set({
      design: prev,
      past: s.past.slice(0, -1),
      future: [snapshot(s.design), ...s.future.slice(0, 49)],
      canUndo: s.past.length > 1,
      canRedo: true,
    });
  },

  redo: () => {
    const s = get();
    if (s.future.length === 0) return;
    const next = s.future[0];
    set({
      design: next,
      future: s.future.slice(1),
      past: [...s.past.slice(-49), snapshot(s.design)],
      canUndo: true,
      canRedo: s.future.length > 1,
    });
  },
}));

/** Room bounds (for camera framing / floorplan export). Safe for empty/partial polygons. */
export function roomBounds(pts: [number, number][]) {
  if (pts.length === 0) {
    return { minX: -1500, maxX: 1500, minZ: -1000, maxZ: 1000, cx: 0, cz: 0 };
  }
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (const [x, z] of pts) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minZ = Math.min(minZ, z);
    maxZ = Math.max(maxZ, z);
  }
  return { minX, maxX, minZ, maxZ, cx: (minX + maxX) / 2, cz: (minZ + maxZ) / 2 };
}

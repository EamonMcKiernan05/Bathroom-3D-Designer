import { create } from 'zustand';
import type { DesignData, PlacedItem, RoomState, TextureAssignment, WallOpening, WallSpec } from '../lib/types';
import { buildWalls, polygonCentroid } from '../lib/geometry';

export const DEFAULT_CEILING = 2400;
export const DEFAULT_WALL_THICKNESS = 100;

/** Auto-generate one rectangular wall per floor edge. */
export function wallsFromFloor(
  floorPoints: [number, number][],
  ceilingHeight: number,
  thickness: number,
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
      height: ceilingHeight,
      profile: 'rectangle',
      slopeRise: 0,
      stairSteps: 6,
      boxLength: Math.round((b[0] - a[0] || b[1] - a[1]) / 2),
      boxDepth: 120,
      boxFrom: 150,
      boxTop: 450,
    });
  }
  return walls;
}

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
        room: { ...st.design.room, floorPoints: [], walls: [], closed: false },
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
    set((st) => ({
      design: {
        ...st.design,
        room: {
          ...room,
          floorPoints: cleaned,
          walls: wallsFromFloor(cleaned, room.ceilingHeight, room.wallThickness),
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

  setCeilingHeight: (h) =>
    get().setRoom({
      ...get().design.room,
      ceilingHeight: h,
      walls: get().design.room.walls.map((w) => (w.profile === 'rectangle' && w.height === get().design.room.ceilingHeight ? { ...w, height: h } : w)),
    }),

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

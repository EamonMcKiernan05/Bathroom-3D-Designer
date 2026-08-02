import { create } from 'zustand';

export type EditorMode = 'navigate' | 'draw' | 'place' | 'surfaces' | 'openings';
export type CameraMode = '3d' | '2d';

interface EditorStore {
  mode: EditorMode;
  cameraMode: CameraMode;
  showGrid: boolean;
  showDimensions: boolean;
  snapEnabled: boolean;
  catalogueOpen: boolean;
  /** current drag product payload (set on dragstart from catalogue) */
  dragProduct: unknown | null;
  openingType: 'door' | 'window';
  setMode: (m: EditorMode) => void;
  setCameraMode: (m: CameraMode) => void;
  toggleGrid: () => void;
  toggleDimensions: () => void;
  toggleSnap: () => void;
  setCatalogueOpen: (open: boolean) => void;
  setDragProduct: (p: unknown | null) => void;
  setOpeningType: (t: 'door' | 'window') => void;
}

export const useEditorStore = create<EditorStore>()((set) => ({
  mode: 'navigate',
  cameraMode: '3d',
  showGrid: true,
  showDimensions: true,
  snapEnabled: true,
  catalogueOpen: true,
  dragProduct: null,
  openingType: 'door',
  setMode: (m) => set({ mode: m }),
  setCameraMode: (m) => set({ cameraMode: m }),
  toggleGrid: () => set((s) => ({ showGrid: !s.showGrid })),
  toggleDimensions: () => set((s) => ({ showDimensions: !s.showDimensions })),
  toggleSnap: () => set((s) => ({ snapEnabled: !s.snapEnabled })),
  setCatalogueOpen: (open) => set({ catalogueOpen: open }),
  setDragProduct: (p) => set({ dragProduct: p }),
  setOpeningType: (t) => set({ openingType: t }),
}));

/** Mount height (mm from floor) for wall-mounted products by category prefix. */
export function mountHeightFor(category?: string): number {
  const c = category ?? '';
  if (c.includes('mirror')) return 1500;
  if (c.includes('cabinet')) return 1550;
  if (c.includes('towel-rail')) return 900;
  if (c.includes('radiator')) return 200;
  if (c.includes('shelf')) return 1300;
  if (c.includes('robe-hook')) return 1300;
  if (c.includes('towel-ring')) return 1150;
  if (c.includes('soap-dish')) return 1150;
  if (c.includes('shower-head')) return 2050;
  if (c.includes('shower-set')) return 0; // valve sits at model height
  if (c.includes('shower-screen')) return 0;
  return 0;
}

export function isWallMounted(category?: string): boolean {
  const c = category ?? '';
  return (
    c.includes('mirror') ||
    c.includes('cabinet') ||
    c.includes('towel-rail') ||
    c.includes('radiator') ||
    c.includes('shelf') ||
    c.includes('robe-hook') ||
    c.includes('towel-ring') ||
    c.includes('soap-dish') ||
    c.includes('shower-head') ||
    c.includes('shower-set') ||
    c.includes('tap')
  );
}

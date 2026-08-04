import { useMemo, useRef, useState } from 'react';
import { buildWalls, cornerAnglesDeg } from '../../lib/geometry';
import { ROOM_TEMPLATES, templateRoom, useDesignStore } from '../../stores/design-store';
import { useEditorStore, type EditorMode } from '../../stores/editor-store';
import { api } from '../../lib/api';
import { WallProperties } from './WallProperties';
import { CatalogueBrowser } from '../catalogue/CatalogueBrowser';
import { TexturePicker } from '../surfaces/TexturePicker';
import type { Product, WallSpec } from '../../lib/types';

/* ------------------------------------------------------------------ */
/* Shared bits                                                         */
/* ------------------------------------------------------------------ */

const sectionTitle = 'mb-1 text-xs font-semibold text-neutral-600';
const inputCls = 'w-24 rounded border border-neutral-300 px-1.5 py-0.5 text-right';

/** Room dimensions block — ceiling acts as a MAX height cap. */
function RoomDimensions() {
  const room = useDesignStore((s) => s.design.room);
  const setCeilingHeight = useDesignStore((s) => s.setCeilingHeight);
  const setWallThickness = useDesignStore((s) => s.setWallThickness);
  const walls = useMemo(() => (room.closed ? buildWalls(room.floorPoints) : []), [room]);
  if (!room.closed) return null;
  return (
    <div>
      <p className={sectionTitle}>Room dimensions</p>
      <div className="space-y-1.5">
        <label className="flex items-center justify-between text-xs" title="Walls above this height are pulled down to it; shorter walls stay unchanged">
          <span>Ceiling max height</span>
          <input
            type="number"
            value={room.ceilingHeight}
            onChange={(e) => setCeilingHeight(Math.max(500, Number(e.target.value) || 2400))}
            className={inputCls}
          />
        </label>
        <label className="flex items-center justify-between text-xs">
          <span>Wall thickness</span>
          <input
            type="number"
            value={room.wallThickness}
            onChange={(e) => setWallThickness(Math.max(40, Number(e.target.value) || 100))}
            className={inputCls}
          />
        </label>
        {walls.map((w, i) => (
          <p key={i} className="text-[11px] text-neutral-500">
            Wall {i + 1}: {Math.round(w.length)} mm
          </p>
        ))}
      </div>
    </div>
  );
}

/** Editable wall lengths — typing a new length keeps the room connected. */
function WallLengthInputs() {
  const room = useDesignStore((s) => s.design.room);
  const setWallLength = useDesignStore((s) => s.setWallLength);
  const walls = useMemo(() => (room.closed ? buildWalls(room.floorPoints) : []), [room]);
  if (!room.closed) return null;
  return (
    <div>
      <p className={sectionTitle}>Wall lengths</p>
      <p className="mb-1.5 text-[10px] text-neutral-400">
        Adjacent walls follow the shared corner so the room stays connected.
      </p>
      <div className="space-y-1.5">
        {walls.map((w, i) => (
          <label key={i} className="flex items-center justify-between text-xs">
            <span>Wall {i + 1}</span>
            <span className="flex items-center gap-1">
              <input
                type="number"
                value={Math.round(w.length)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (Number.isFinite(v) && v >= 100) setWallLength(i, v);
                }}
                className={inputCls}
              />
              <span className="text-[10px] text-neutral-400">mm</span>
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

/** Doors & windows list + add form. */
function DoorsWindowsSection() {
  const room = useDesignStore((s) => s.design.room);
  const doors = useDesignStore((s) => s.design.doors);
  const windows = useDesignStore((s) => s.design.windows);
  const removeOpening = useDesignStore((s) => s.removeOpening);
  const walls = useMemo(() => (room.closed ? buildWalls(room.floorPoints) : []), [room]);
  return (
    <div>
      <p className={sectionTitle}>Doors & windows</p>
      {doors.length + windows.length === 0 && <p className="text-xs text-neutral-400">None yet.</p>}
      {[...doors.map((d) => ({ ...d, kind: 'door' as const })), ...windows.map((w) => ({ ...w, kind: 'window' as const }))].map((o) => (
        <div key={o.id} className="mb-1 flex items-center justify-between rounded border border-neutral-200 px-2 py-1 text-xs">
          <span>
            {o.kind === 'door' ? '🚪' : '🪟'} wall {o.wallIndex + 1} · {Math.round(o.pos)}mm
          </span>
          <button onClick={() => removeOpening(o.id)} className="text-neutral-400 hover:text-red-500" title="Remove">
            ✕
          </button>
        </div>
      ))}
      {room.closed && <OpeningForm wallCount={walls.length} onAdd={(o) => useDesignStore.getState().addOpening(o)} />}
    </div>
  );
}

/** Items list (click to select, toggle visibility, delete). */
function ItemsList() {
  const items = useDesignStore((s) => s.design.items);
  const selectedItemId = useDesignStore((s) => s.selectedItemId);
  const selectItem = useDesignStore((s) => s.selectItem);
  const removeItem = useDesignStore((s) => s.removeItem);
  const updateItem = useDesignStore((s) => s.updateItem);
  return (
    <div className="space-y-1">
      {items.length === 0 && <p className="text-xs text-neutral-400">No items placed. Add products from the catalogue panel on the right.</p>}
      {items.map((it) => (
        <div
          key={it.id}
          onClick={() => selectItem(it.id)}
          className={`flex cursor-pointer items-center justify-between rounded border px-2 py-1.5 text-xs ${
            selectedItemId === it.id ? 'border-sky-500 bg-sky-50' : 'border-neutral-200 hover:border-neutral-300'
          }`}
        >
          <span className="truncate">{it.name}</span>
          <div className="flex shrink-0 items-center gap-1">
            <button
              onClick={(e) => {
                e.stopPropagation();
                updateItem(it.id, { visible: !(it as unknown as { visible?: boolean }).visible });
              }}
              className="text-neutral-400 hover:text-neutral-700"
              title="Toggle visibility"
            >
              {(it as unknown as { visible?: boolean }).visible === false ? '🙈' : '👁️'}
            </button>
            <button onClick={(e) => { e.stopPropagation(); removeItem(it.id); }} className="text-neutral-400 hover:text-red-500" title="Delete">
              🗑
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Selected item properties (position / rotation). */
function ItemProperties() {
  const selectedItemId = useDesignStore((s) => s.selectedItemId);
  const items = useDesignStore((s) => s.design.items);
  const updateItem = useDesignStore((s) => s.updateItem);
  const rotateItem = useDesignStore((s) => s.rotateItem);
  const removeItem = useDesignStore((s) => s.removeItem);
  const item = items.find((i) => i.id === selectedItemId) ?? null;
  if (!item) return <p className="text-xs text-neutral-400">Select an item in the 3D view or the list above to edit it.</p>;
  return (
    <div className="space-y-3 text-xs">
      <div>
        <p className="font-medium text-neutral-800">{item.name}</p>
        <p className="text-neutral-500">
          {item.retailerName ?? '—'} · {item.sku ?? ''} · {item.finish ?? ''}
        </p>
        {item.price != null && <p className="mt-0.5 font-semibold text-neutral-900">£{Number(item.price).toFixed(2)}</p>}
      </div>
      <label className="block">
        <span className="text-neutral-500">Position X (mm)</span>
        <input
          type="number"
          value={Math.round(item.position[0])}
          onChange={(e) => updateItem(item.id, { position: [Number(e.target.value) || 0, item.position[1], item.position[2]] })}
          className="mt-0.5 w-full rounded border border-neutral-300 px-1.5 py-1"
        />
      </label>
      <label className="block">
        <span className="text-neutral-500">Position Y (mm)</span>
        <input
          type="number"
          value={Math.round(item.position[1])}
          onChange={(e) => updateItem(item.id, { position: [item.position[0], Number(e.target.value) || 0, item.position[2]] })}
          className="mt-0.5 w-full rounded border border-neutral-300 px-1.5 py-1"
        />
      </label>
      <label className="block">
        <span className="text-neutral-500">Position Z (mm)</span>
        <input
          type="number"
          value={Math.round(item.position[2])}
          onChange={(e) => updateItem(item.id, { position: [item.position[0], item.position[1], Number(e.target.value) || 0] })}
          className="mt-0.5 w-full rounded border border-neutral-300 px-1.5 py-1"
        />
      </label>
      <label className="block">
        <span className="text-neutral-500">Rotation (deg)</span>
        <input
          type="number"
          value={Math.round((item.rotation * 180) / Math.PI)}
          onChange={(e) => rotateItem(item.id, ((Number(e.target.value) || 0) * Math.PI) / 180)}
          className="mt-0.5 w-full rounded border border-neutral-300 px-1.5 py-1"
        />
      </label>
      <div className="flex gap-1">
        <button onClick={() => rotateItem(item.id, item.rotation + Math.PI / 2)} className="flex-1 rounded border border-neutral-300 py-1.5 hover:bg-neutral-50">
          Rotate 90° (R)
        </button>
        <button onClick={() => removeItem(item.id)} className="flex-1 rounded border border-red-200 py-1.5 text-red-600 hover:bg-red-50">
          Delete
        </button>
      </div>
      <p className="text-[10px] text-neutral-400">Tip: drag the item in the 3D view to move it. It snaps to walls when close.</p>
    </div>
  );
}

/** Templates + photo-plan import. */
function StartSection() {
  const setRoom = useDesignStore((s) => s.setRoom);
  const fileRef = useRef<HTMLInputElement>(null);
  const [planError, setPlanError] = useState('');
  const [planBusy, setPlanBusy] = useState(false);

  const onPlanFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setPlanBusy(true);
    setPlanError('');
    try {
      const plan = await api.uploadPlanPhoto(file);
      const floor = (plan.floor ?? []) as [number, number][];
      if (floor.length < 3) throw new Error('No usable outline in the photo result');
      const ceiling = plan.ceilingHeight ?? 2400;
      const thickness = plan.wallThickness ?? 100;
      const wallSpecs: WallSpec[] = floor.map((a, i) => {
        const b = floor[(i + 1) % floor.length];
        const pw = plan.walls?.[i] ?? {};
        return {
          id: crypto.randomUUID(),
          outline: [a, b],
          thickness,
          height: pw.height ?? ceiling,
          profile: pw.profile ?? 'rectangle',
          slopeRise: pw.slopeRise ?? 0,
          stairSteps: pw.stairSteps ?? 6,
          boxLength: pw.boxLength ?? 0,
          boxDepth: pw.boxDepth ?? 120,
          boxFrom: pw.boxFrom ?? 0,
          boxTop: pw.boxTop ?? 450,
          cornerA: i,
          cornerB: (i + 1) % floor.length,
          topPoints: [],
        };
      });
      useDesignStore.getState().setRoom({ floorPoints: floor, walls: wallSpecs, ceilingHeight: ceiling, wallThickness: thickness, closed: true, cornerHeights: floor.map(() => ceiling) });
      // Importing a new plan replaces the room — clear any prior doors/windows/items first.
      useDesignStore.getState().clearRoomContents();
      const st = useDesignStore.getState();
      (plan.doors ?? []).forEach((d: any) =>
        st.addOpening({ id: crypto.randomUUID(), type: 'door', wallIndex: d.wall ?? 0, pos: d.pos ?? 0, width: d.width ?? 850, height: d.height ?? 2100, sillHeight: 0 }),
      );
      (plan.windows ?? []).forEach((w: any) =>
        st.addOpening({ id: crypto.randomUUID(), type: 'window', wallIndex: w.wall ?? 0, pos: w.pos ?? 0, width: w.width ?? 1100, height: w.height ?? 1200, sillHeight: w.sill ?? 900 }),
      );
      useEditorStore.getState().setMode('walls');
    } catch (err) {
      setPlanError(String(err).slice(0, 200));
    } finally {
      setPlanBusy(false);
    }
  };

  return (
    <>
      <div>
        <p className={sectionTitle}>Start from a template</p>
        <div className="flex flex-wrap gap-1">
          {ROOM_TEMPLATES.map((t) => (
            <button
              key={t.name}
              onClick={() => setRoom(templateRoom(t.w, t.d, t.ceiling))}
              className="rounded border border-neutral-300 px-2 py-1 text-[11px] text-neutral-700 hover:border-sky-400 hover:text-sky-700"
              title={`${t.w}x${t.d}mm, ${t.ceiling}mm ceiling`}
            >
              {t.name}
            </button>
          ))}
        </div>
      </div>
      <div>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={planBusy}
          className="w-full rounded border border-dashed border-sky-300 bg-sky-50 px-2 py-1.5 text-[11px] font-medium text-sky-700 hover:bg-sky-100 disabled:opacity-50"
        >
          {planBusy ? '📷 Reading photo…' : '📷 Import plan from photo'}
        </button>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onPlanFile} />
        {planError && <p className="mt-1 text-[10px] text-red-600">{planError}</p>}
        <p className="mt-1 text-[10px] text-neutral-400">
          Upload a clear photo of a hand-drawn plan / measurements — a local vision model (Gemma 4 edge) turns it into this room.
        </p>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Per-view LEFT sidebar                                               */
/* ------------------------------------------------------------------ */

export const VIEW_TITLES: Record<EditorMode, string> = {
  navigate: 'Scene',
  draw: 'Draw Room',
  walls: 'Edit Walls',
  openings: 'Doors & Windows',
  place: 'Place Items',
  surfaces: 'Surfaces',
  measure: 'Measure',
};

/** One left sidebar per view — content relevant to the active canvas. */
export function ViewSidebar({ mode }: { mode: EditorMode }) {
  const room = useDesignStore((s) => s.design.room);
  const selectedSurface = useDesignStore((s) => s.selectedSurface);
  const setMode = useEditorStore((s) => s.setMode);
  const measure = useEditorStore((s) => s.measure);

  let body: React.ReactNode;
  switch (mode) {
    case 'draw':
      body = room.closed ? (
        <>
          <RoomDimensions />
          <WallLengthInputs />
          <p className="text-[10px] text-neutral-400">
            Double-click a corner on the plan to delete it · right-click a wall to add one.
          </p>
        </>
      ) : (
        <>
          <p className="text-xs text-amber-600">Drawing mode — click the floor to add points, then finish below.</p>
          <button
            onClick={() => useDesignStore.getState().closePolygon()}
            className="mt-2 w-full rounded bg-emerald-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
          >
            Finish room ({room.floorPoints.length} points)
          </button>
          <button
            onClick={() => useDesignStore.getState().undoPoint()}
            className="mt-1 w-full rounded border border-neutral-300 px-2 py-1 text-xs text-neutral-600 hover:bg-neutral-50"
          >
            Undo last point
          </button>
        </>
      );
      break;
    case 'walls':
      body = <WallProperties />;
      break;
    case 'openings':
      body = (
        <>
          <DoorsWindowsSection />
          <p className="mt-2 text-[10px] text-neutral-400">You can also click a wall in the 3D view to drop the selected opening type at that spot.</p>
        </>
      );
      break;
    case 'place':
      body = (
        <>
          <p className={sectionTitle}>Items</p>
          <ItemsList />
          <div className="mt-3 border-t border-neutral-100 pt-3">
            <ItemProperties />
          </div>
        </>
      );
      break;
    case 'surfaces':
      body = selectedSurface ? (
        <div className="space-y-2 text-xs">
          <p className="font-medium text-neutral-800">
            {selectedSurface.type === 'floor' ? 'Floor' : selectedSurface.type === 'ceiling' ? 'Ceiling' : `Wall ${selectedSurface.index + 1}`} selected
          </p>
          <p className="text-neutral-500">Pick a tile or colour from the library panel on the right to apply it.</p>
        </div>
      ) : (
        <p className="text-xs text-neutral-400">Click a wall, the floor or the ceiling in the 3D view, then pick a finish from the library panel.</p>
      );
      break;
    case 'measure': {
      const dist =
        measure?.a && measure.b
          ? Math.round(Math.hypot(measure.b[0] - measure.a[0], measure.b[1] - measure.a[1]))
          : null;
      body = (
        <div className="space-y-2 text-xs">
          <p className="text-neutral-500">Click two points on the floor to measure between them. Esc clears the measurement.</p>
          {dist != null ? (
            <p className="rounded bg-sky-50 px-2 py-1.5 font-semibold text-sky-800">{dist} mm</p>
          ) : (
            <p className="text-neutral-400">{measure ? 'One point set — click the second point.' : 'No measurement yet.'}</p>
          )}
        </div>
      );
      break;
    }
    case 'navigate':
    default:
      body = (
        <>
          <StartSection />
          <RoomDimensions />
          <DoorsWindowsSection />
          <div className="mt-3 border-t border-neutral-100 pt-3">
            <p className={sectionTitle}>Items</p>
            <ItemsList />
          </div>
        </>
      );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-neutral-200 px-3 py-2 text-xs font-semibold text-neutral-600">{VIEW_TITLES[mode]}</div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">{body}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* RIGHT library panel — the old bottom bar, moved to the right        */
/* ------------------------------------------------------------------ */

export function LibraryPanel({ onAddToDesign }: { onAddToDesign: (p: Product) => void }) {
  const [tab, setTab] = useState<'catalogue' | 'surfaces'>('catalogue');
  const [surfaceCat, setSurfaceCat] = useState('wall-tiles');

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-1 border-b border-neutral-200 px-2">
        <button
          onClick={() => setTab('catalogue')}
          className={`px-3 py-1.5 text-xs font-medium ${tab === 'catalogue' ? 'border-b-2 border-sky-600 text-sky-700' : 'text-neutral-500'}`}
        >
          🛒 Catalogue
        </button>
        <button
          onClick={() => setTab('surfaces')}
          className={`px-3 py-1.5 text-xs font-medium ${tab === 'surfaces' ? 'border-b-2 border-sky-600 text-sky-700' : 'text-neutral-500'}`}
        >
          🧱 Surfaces
        </button>
      </div>
      {tab === 'surfaces' && (
        <div className="flex flex-wrap gap-1 border-b border-neutral-200 px-2 py-1.5">
          {['wall-tiles', 'floor-tiles', 'panels', 'ceiling'].map((c) => (
            <button
              key={c}
              onClick={() => setSurfaceCat(c)}
              className={`rounded px-2 py-0.5 text-[11px] capitalize ${surfaceCat === c ? 'bg-sky-600 text-white' : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'}`}
            >
              {c.replace('-', ' ')}
            </button>
          ))}
        </div>
      )}
      <div className="min-h-0 flex-1">
        {tab === 'catalogue' ? <CatalogueBrowser onAddToDesign={onAddToDesign} /> : <TexturePicker category={surfaceCat} />}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Opening form (shared)                                               */
/* ------------------------------------------------------------------ */

/** Standalone form to add a door/window to a specific wall — no canvas clicking needed. */
function OpeningForm({
  wallCount,
  onAdd,
}: {
  wallCount: number;
  onAdd: (o: {
    id: string;
    type: 'door' | 'window';
    wallIndex: number;
    pos: number;
    width: number;
    height: number;
    sillHeight: number;
  }) => void;
}) {
  const [type, setType] = useState<'door' | 'window'>('door');
  const [wallIndex, setWallIndex] = useState(0);
  const [pos, setPos] = useState(600);
  const [width, setWidth] = useState(900);
  const [height, setHeight] = useState(2100);
  const [sill, setSill] = useState(900);
  const room = useDesignStore((s) => s.design.room);
  const walls = useMemo(() => (room.closed ? buildWalls(room.floorPoints) : []), [room]);
  const maxPos = walls[wallIndex]?.length ?? 2000;

  const add = () => {
    onAdd({
      id: crypto.randomUUID(),
      type,
      wallIndex,
      pos: Math.max(50, Math.min(maxPos - 50, pos)),
      width,
      height,
      sillHeight: type === 'door' ? 0 : sill,
    });
  };

  const labelCls = 'block text-[10px] text-neutral-500';
  const inputCls2 = 'w-full rounded border border-neutral-300 px-1.5 py-0.5 text-xs';

  return (
    <div className="mt-2 rounded border border-neutral-200 bg-neutral-50 p-2">
      <div className="grid grid-cols-2 gap-1.5">
        <label className={labelCls}>
          Type
          <select value={type} onChange={(e) => setType(e.target.value as 'door' | 'window')} className={inputCls2}>
            <option value="door">Door (800-1000mm)</option>
            <option value="window">Window</option>
          </select>
        </label>
        <label className={labelCls}>
          Wall
          <select value={wallIndex} onChange={(e) => setWallIndex(Number(e.target.value))} className={inputCls2}>
            {walls.map((w, idx) => (
              <option key={idx} value={idx}>
                Wall {idx + 1} ({Math.round(w.length)}mm)
              </option>
            ))}
          </select>
        </label>
        <label className={labelCls}>
          Position along wall (mm)
          <input type="number" value={pos} min={50} max={Math.max(100, maxPos - 50)} onChange={(e) => setPos(Number(e.target.value))} className={inputCls2} />
        </label>
        <label className={labelCls}>
          Width (mm)
          <input type="number" value={width} onChange={(e) => setWidth(Number(e.target.value))} className={inputCls2} />
        </label>
        <label className={labelCls}>
          Height (mm)
          <input type="number" value={height} onChange={(e) => setHeight(Number(e.target.value))} className={inputCls2} />
        </label>
        {type === 'window' && (
          <label className={labelCls}>
            Sill height (mm)
            <input type="number" value={sill} onChange={(e) => setSill(Number(e.target.value))} className={inputCls2} />
          </label>
        )}
      </div>
      <button onClick={add} className="mt-1.5 w-full rounded bg-sky-600 px-2 py-1 text-xs font-medium text-white hover:bg-sky-700">
        + Add {type}
      </button>
    </div>
  );
}

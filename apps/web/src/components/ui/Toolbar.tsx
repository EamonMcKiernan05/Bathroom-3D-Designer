import { useDesignStore } from '../../stores/design-store';
import { useEditorStore, type EditorMode } from '../../stores/editor-store';

const MODES: { id: EditorMode; label: string; icon: string; hint: string }[] = [
  { id: 'navigate', label: 'Navigate', icon: '✋', hint: 'Orbit / select items' },
  { id: 'draw', label: 'Draw Room', icon: '📐', hint: 'Click floor to place wall points, right-click to undo, Esc to cancel' },
  { id: 'openings', label: 'Doors & Windows', icon: '🚪', hint: 'Click a wall to add an opening' },
  { id: 'place', label: 'Place Items', icon: '🛁', hint: 'Drag from catalogue below, or click a placed item and drag it' },
  { id: 'surfaces', label: 'Surfaces', icon: '🧱', hint: 'Click a wall/floor/ceiling to apply textures or paint' },
  { id: 'measure', label: 'Measure', icon: '📏', hint: 'Click two points to measure a distance; Esc to clear' },
];

export function Toolbar({ onSave, onExport, onNew }: { onSave: () => void; onExport: () => void; onNew: () => void }) {
  const mode = useEditorStore((s) => s.mode);
  const setMode = useEditorStore((s) => s.setMode);
  const cameraMode = useEditorStore((s) => s.cameraMode);
  const setCameraMode = useEditorStore((s) => s.setCameraMode);
  const showGrid = useEditorStore((s) => s.showGrid);
  const toggleGrid = useEditorStore((s) => s.toggleGrid);
  const canUndo = useDesignStore((s) => s.canUndo);
  const canRedo = useDesignStore((s) => s.canRedo);
  const undo = useDesignStore((s) => s.undo);
  const redo = useDesignStore((s) => s.redo);
  const designName = useDesignStore((s) => s.designName);
  const setDesignName = useDesignStore((s) => s.setDesignName);
  const savedAt = useDesignStore((s) => s.savedAt);
  const designId = useDesignStore((s) => s.designId);
  const items = useDesignStore((s) => s.design.items);

  const active = MODES.find((m) => m.id === mode)!;

  return (
    <div className="flex items-center gap-1 border-b border-neutral-200 bg-white px-2 py-1.5">
      <span className="mr-1 text-sm font-bold text-neutral-800">🛁 Bathroom 3D</span>
      <div className="flex items-center gap-0.5 rounded-lg bg-neutral-100 p-0.5">
        {MODES.map((m) => (
          <button
            key={m.id}
            onClick={() => {
              setMode(m.id);
              if (m.id === 'draw') useDesignStore.getState().startDrawing();
            }}
            title={m.hint}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
              mode === m.id ? 'bg-white text-sky-700 shadow' : 'text-neutral-600 hover:text-neutral-900'
            }`}
          >
            {m.icon} {m.label}
          </button>
        ))}
      </div>

      <div className="mx-1 h-5 w-px bg-neutral-200" />

      <div className="flex items-center gap-0.5">
        <button
          onClick={undo}
          disabled={!canUndo}
          title="Undo (Ctrl+Z)"
          className="rounded px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-100 disabled:opacity-30"
        >
          ↶ Undo
        </button>
        <button
          onClick={redo}
          disabled={!canRedo}
          title="Redo (Ctrl+Shift+Z)"
          className="rounded px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-100 disabled:opacity-30"
        >
          ↷
        </button>
        <button
          onClick={() => setCameraMode(cameraMode === '3d' ? '2d' : '3d')}
          title="Toggle 2D/3D (/)"
          className={`rounded px-2 py-1 text-xs ${cameraMode === '2d' ? 'bg-sky-100 text-sky-700' : 'text-neutral-700 hover:bg-neutral-100'}`}
        >
          {cameraMode === '3d' ? '2D Top' : '3D'}
        </button>
        <button
          onClick={toggleGrid}
          title="Toggle grid (G)"
          className={`rounded px-2 py-1 text-xs ${showGrid ? 'text-neutral-700 hover:bg-neutral-100' : 'text-neutral-400'}`}
        >
          ▦ Grid
        </button>
      </div>

      <div className="mx-1 h-5 w-px bg-neutral-200" />

      <div className="flex min-w-0 flex-1 items-center gap-2">
        <input
          value={designName}
          onChange={(e) => setDesignName(e.target.value)}
          className="w-48 rounded border border-transparent px-1.5 py-0.5 text-xs text-neutral-800 outline-none hover:border-neutral-300 focus:border-sky-500"
        />
        {designId ? (
          <span className="whitespace-nowrap text-[10px] text-emerald-600">saved{designId ? ` #${designId}` : ''}{savedAt ? ` · ${savedAt}` : ''}</span>
        ) : (
          <span className="text-[10px] text-neutral-400">not saved yet</span>
        )}
        <span className="ml-auto whitespace-nowrap text-[10px] text-neutral-400">{items.length} item{items.length === 1 ? '' : 's'}</span>
      </div>

      <div className="flex items-center gap-1">
        <button onClick={onNew} className="rounded border border-neutral-300 px-2.5 py-1 text-xs text-neutral-700 hover:bg-neutral-50">
          New
        </button>
        <button onClick={onSave} className="rounded bg-sky-600 px-3 py-1 text-xs font-medium text-white hover:bg-sky-700">
          Save
        </button>
        <button onClick={onExport} className="rounded bg-neutral-800 px-3 py-1 text-xs font-medium text-white hover:bg-neutral-900">
          Export BOM
        </button>
      </div>
    </div>
  );
}

export function ModeHint() {
  const mode = useEditorStore((s) => s.mode);
  const openingType = useEditorStore((s) => s.openingType);
  const active = MODES.find((m) => m.id === mode)!;
  return (
    <div className="pointer-events-none absolute bottom-16 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded-full bg-black/70 px-4 py-1.5 text-xs text-white backdrop-blur">
      {mode === 'openings' ? `${active.hint} (currently: ${openingType})` : active.hint}
    </div>
  );
}

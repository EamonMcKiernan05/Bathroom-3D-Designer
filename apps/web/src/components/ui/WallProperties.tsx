import { useDesignStore } from '../../stores/design-store';
import { useEditorStore } from '../../stores/editor-store';
import type { WallProfile } from '../../lib/types';

const PROFILES: { id: WallProfile; label: string; desc: string }[] = [
  { id: 'rectangle', label: 'Rectangle', desc: 'Plain vertical wall, full height' },
  { id: 'gable', label: 'Sloped roof', desc: 'Top follows a sloped ceiling (e.g. attic/gable)' },
  { id: 'stairs', label: 'Under stairs', desc: 'Stepped top where a staircase runs above' },
  { id: 'boxing', label: 'Boxing (pipes)', desc: 'Protruding box to hide waste/water pipes' },
];

export function WallProperties() {
  const selectedWallId = useEditorStore((s) => s.selectedWallId) ?? null;
  const walls = useDesignStore((s) => s.design.room.walls);
  const updateWall = useDesignStore((s) => s.updateWall);
  const room = useDesignStore((s) => s.design.room);
  const wall = walls.find((w) => w.id === selectedWallId) ?? null;

  if (!wall) {
    return (
      <div className="p-3 text-xs text-neutral-400">
        Click a wall in the plan to edit its shape — rectangle, sloped roof (attic), under stairs, or a
        boxing/bulkhead to hide pipes.
      </div>
    );
  }

  const idx = walls.indexOf(wall);
  const length = Math.hypot(
    wall.outline[wall.outline.length - 1][0] - wall.outline[0][0],
    wall.outline[wall.outline.length - 1][1] - wall.outline[0][1],
  );

  const set = (patch: Parameters<typeof updateWall>[1]) => updateWall(wall.id, patch);

  const labelCls = 'block text-[10px] text-neutral-500';
  const inputCls = 'w-full rounded border border-neutral-300 px-1.5 py-1 text-xs';

  return (
    <div className="p-3 text-xs">
      <div className="mb-2 font-medium text-neutral-800">
        Wall {idx + 1} · {Math.round(length)} mm
      </div>

      <div className="mb-2 space-y-1">
        {PROFILES.map((p) => (
          <button
            key={p.id}
            onClick={() => {
              // sensible defaults so a chosen shape is immediately visible
              const patch: Parameters<typeof updateWall>[1] = { profile: p.id };
              if (p.id === 'gable' && !wall.slopeRise) patch.slopeRise = 800;
              set(patch);
            }}
            className={`block w-full rounded border px-2 py-1.5 text-left transition ${
              wall.profile === p.id ? 'border-sky-500 bg-sky-50 text-sky-800' : 'border-neutral-200 text-neutral-700 hover:border-neutral-300'
            }`}
          >
            <span className="font-medium">{p.label}</span>
            <span className="block text-[10px] text-neutral-500">{p.desc}</span>
          </button>
        ))}
      </div>

      <label className={labelCls}>
        Height (mm)
        <input type="number" value={wall.height} onChange={(e) => set({ height: Number(e.target.value) || 0 })} className={inputCls} />
      </label>

      {wall.profile === 'gable' && (
        <label className={labelCls}>
          Top rise (mm) — extra height at the high end
          <input type="number" value={wall.slopeRise} onChange={(e) => set({ slopeRise: Number(e.target.value) || 0 })} className={inputCls} />
        </label>
      )}

      {wall.profile === 'stairs' && (
        <label className={labelCls}>
          Number of steps
          <input type="number" min={2} max={15} value={wall.stairSteps} onChange={(e) => set({ stairSteps: Math.max(2, Number(e.target.value) || 5) })} className={inputCls} />
        </label>
      )}

      {wall.profile === 'boxing' && (
        <div className="mt-1 space-y-1">
          <label className={labelCls}>
            Box length (mm) along wall
            <input type="number" value={wall.boxLength} onChange={(e) => set({ boxLength: Number(e.target.value) || 0 })} className={inputCls} />
          </label>
          <label className={labelCls}>
            Box depth (mm) into room
            <input type="number" value={wall.boxDepth} onChange={(e) => set({ boxDepth: Number(e.target.value) || 0 })} className={inputCls} />
          </label>
          <label className={labelCls}>
            Box start (mm) from wall end
            <input type="number" value={wall.boxFrom} onChange={(e) => set({ boxFrom: Number(e.target.value) || 0 })} className={inputCls} />
          </label>
          <label className={labelCls}>
            Box height (mm) from floor
            <input type="number" value={wall.boxTop} onChange={(e) => set({ boxTop: Number(e.target.value) || 0 })} className={inputCls} />
          </label>
        </div>
      )}

      <div className="mt-3 flex gap-1">
        <button
          onClick={() => set({ height: room.ceilingHeight })}
          className="flex-1 rounded border border-neutral-300 py-1 text-[11px] text-neutral-600 hover:bg-neutral-50"
        >
          Full height
        </button>
        <button
          onClick={() => useEditorStore.getState().setSelectedWall(null)}
          className="flex-1 rounded border border-neutral-300 py-1 text-[11px] text-neutral-600 hover:bg-neutral-50"
        >
          Deselect
        </button>
      </div>
      <p className="mt-2 text-[10px] text-neutral-400">Shaped walls render without tile textures for now; switch back to Rectangle to tile.</p>
    </div>
  );
}

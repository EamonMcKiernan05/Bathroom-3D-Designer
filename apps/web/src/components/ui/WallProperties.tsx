import { useMemo } from 'react';
import { useDesignStore, cornerHeightsFor } from '../../stores/design-store';
import { useEditorStore } from '../../stores/editor-store';
import { cornerAnglesDeg } from '../../lib/geometry';

export function WallProperties() {
  const selectedWallId = useEditorStore((s) => s.selectedWallId) ?? null;
  const walls = useDesignStore((s) => s.design.room.walls);
  const updateWall = useDesignStore((s) => s.updateWall);
  const room = useDesignStore((s) => s.design.room);
  const setHeights = useDesignStore((s) => s.setWallHeights);
  const wall = walls.find((w) => w.id === selectedWallId) ?? walls[0] ?? null;

  // interior angles at each corner — visual only
  const angles = useMemo(
    () => (room.closed && room.floorPoints.length >= 3 ? cornerAnglesDeg(room.floorPoints) : []),
    [room.floorPoints, room.closed],
  );

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

  const n = room.floorPoints.length;
  const ch = cornerHeightsFor(room);
  const ca = wall.cornerA ?? idx;
  const cb = wall.cornerB ?? (idx + 1) % n;
  const hA = ch[ca] ?? wall.height;
  const hB = ch[cb] ?? wall.height;
  const uniform = Math.abs(hA - hB) < 1;

  const labelCls = 'block text-[10px] text-neutral-500';
  const inputCls = 'w-full rounded border border-neutral-300 px-1.5 py-1 text-xs';

  return (
    <div className="p-3 text-xs">
      <div className="mb-2 font-medium text-neutral-800">
        Wall {idx + 1} · {Math.round(length)} mm
      </div>

      {/* corner angles — display only, not editable */}
      <div className="mb-2 rounded bg-neutral-50 px-2 py-1.5 text-[11px] text-neutral-600">
        Corner angles: end A <span className="font-semibold">{Math.round(angles[ca] ?? 0)}°</span> · end B{' '}
        <span className="font-semibold">{Math.round(angles[cb] ?? 0)}°</span>
      </div>

      <label className={labelCls}>
        Height (mm) — both ends
        <input
          type="number"
          value={uniform ? Math.round(hA) : Math.round((hA + hB) / 2)}
          onChange={(e) => {
            const h = Number(e.target.value) || 0;
            setHeights(wall.id, h, h);
          }}
          className={inputCls}
        />
      </label>

      {wall.profile === 'rectangle' && (
        <div className="mt-1 space-y-1">
          <label className={labelCls}>
            End A height (mm) — shared with the previous wall
            <input type="number" value={Math.round(hA)} onChange={(e) => setHeights(wall.id, Number(e.target.value) || 0, hB)} className={inputCls} />
          </label>
          <label className={labelCls}>
            End B height (mm) — shared with the next wall
            <input type="number" value={Math.round(hB)} onChange={(e) => setHeights(wall.id, hA, Number(e.target.value) || 0)} className={inputCls} />
          </label>
          {!uniform && <p className="text-[10px] text-amber-600">Sloped top — {(hB - hA) > 0 ? 'rises' : 'falls'} {Math.round(Math.abs(hB - hA))} mm along the wall</p>}
        </div>
      )}

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
          onClick={() => setHeights(wall.id, room.ceilingHeight, room.ceilingHeight)}
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

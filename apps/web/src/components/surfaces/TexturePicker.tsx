import { useEffect, useMemo, useState } from 'react';
import { api } from '../../lib/api';
import { useDesignStore } from '../../stores/design-store';
import { buildWalls } from '../../lib/geometry';
import type { TextureAssignment, TextureInfo } from '../../lib/types';

const GROUT_COLORS = ['#ffffff', '#d4d4d4', '#9ca3af', '#4b5563', '#000000'];
const PAINT_COLORS = [
  '#f2f1ec', '#e7e4dd', '#d5d0c6', '#b8b2a6', '#8a857b',
  '#f5efe6', '#e8dcc8', '#d9c6a8', '#c4aa86',
  '#e8f0ef', '#cddcdb', '#a9c0bd', '#7da5a1',
  '#eef0f3', '#d3d9e3', '#afb8c9', '#7e8ba3',
  '#f5edea', '#e6d2cc', '#d3aba0', '#b57f72',
  '#2f3437', '#5f666b', '#8c9399',
];

export function TexturePicker({ category }: { category: string }) {
  const [textures, setTextures] = useState<TextureInfo[]>([]);
  const design = useDesignStore((s) => s.design);
  const selectedSurface = useDesignStore((s) => s.selectedSurface);
  const setFloorTexture = useDesignStore((s) => s.setFloorTexture);
  const setWallTexture = useDesignStore((s) => s.setWallTexture);
  const setCeilingTexture = useDesignStore((s) => s.setCeilingTexture);
  const applyToAllWalls = useDesignStore((s) => s.applyToAllWalls);
  const selectSurface = useDesignStore((s) => s.selectSurface);
  const room = useDesignStore((s) => s.design.room);
  const wallCount = useMemo(() => (room.closed ? buildWalls(room.floorPoints).length : 4), [room.floorPoints, room.closed]);

  useEffect(() => {
    api.textures(category).then(setTextures).catch(() => {});
  }, [category]);

  const active: { type: 'floor' | 'ceiling' | 'wall'; index: number } =
    selectedSurface ?? { type: 'floor', index: 0 };

  const surfaceLabel = active.type === 'floor' ? 'Floor' : active.type === 'ceiling' ? 'Ceiling' : `Wall ${active.index + 1}`;

  const current: TextureAssignment | null =
    active.type === 'floor'
      ? design.floorTexture
      : active.type === 'ceiling'
        ? design.ceilingTexture
        : design.wallTextures[active.index] ?? null;

  const apply = (t: TextureInfo) => {
    const assignment: TextureAssignment = {
      textureId: t.id,
      tileWidthMm: t.tile_width_mm,
      tileHeightMm: t.tile_height_mm,
      groutWidthMm: 3,
      groutColor: GROUT_COLORS[1],
      layout: 'straight',
      rotation: 0,
      url: t.albedo_url ?? '',
      name: t.name,
    };
    if (active.type === 'floor') setFloorTexture(assignment);
    else if (active.type === 'ceiling') setCeilingTexture(assignment);
    else setWallTexture(active.index, assignment);
  };

  const updateCurrent = (patch: Partial<TextureAssignment>) => {
    if (!current) return;
    const next = { ...current, ...patch };
    if (active.type === 'floor') setFloorTexture(next);
    else if (active.type === 'ceiling') setCeilingTexture(next);
    else setWallTexture(active.index, next);
  };

  const applyPaint = (color: string) => {
    const assignment: TextureAssignment = {
      textureId: 0,
      tileWidthMm: 0,
      tileHeightMm: 0,
      groutWidthMm: 3,
      groutColor: GROUT_COLORS[1],
      layout: 'straight',
      rotation: 0,
      url: '',
      name: color,
      solidColor: color,
    };
    if (active.type === 'floor') setFloorTexture(assignment);
    else if (active.type === 'ceiling') setCeilingTexture(assignment);
    else setWallTexture(active.index, assignment);
  };

  const clearSurface = () => {
    if (active.type === 'floor') setFloorTexture(null);
    else if (active.type === 'ceiling') setCeilingTexture(null);
    else setWallTexture(active.index, null);
  };

  return (
    <div className="p-3">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-xs text-neutral-500">Target:</span>
        <select
          value={`${active.type}-${active.index}`}
          onChange={(e) => {
            const [type, idx] = e.target.value.split('-');
            selectSurface({ type: type as 'floor' | 'ceiling' | 'wall', index: Number(idx) });
          }}
          className="rounded border border-neutral-300 px-1.5 py-1 text-xs"
        >
          <option value="floor-0">Floor</option>
          <option value="ceiling-0">Ceiling</option>
          {Array.from({ length: wallCount }).map((_, i) => (
            <option key={i} value={`wall-${i}`}>
              Wall {i + 1}
            </option>
          ))}
        </select>
        <div className="ml-auto flex gap-1">
          {active.type === 'wall' && (
            <button
              onClick={() => current && applyToAllWalls(current)}
              className="rounded bg-sky-600 px-2 py-0.5 text-[11px] text-white hover:bg-sky-700"
              title="Apply current texture to all walls"
            >
              All walls
            </button>
          )}
          {current && (
            <button onClick={clearSurface} className="rounded border border-neutral-300 px-2 py-0.5 text-[11px] text-neutral-600 hover:bg-neutral-100">
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="mb-1 text-sm font-semibold text-neutral-700">{surfaceLabel}</div>

      {current && (
        <div className="mb-3 rounded border border-neutral-200 bg-neutral-50 p-2">
          <div className="mb-1.5 flex items-center gap-2">
            {current.solidColor ? (
              <div className="h-10 w-10 rounded object-cover" style={{ background: current.solidColor, border: '1px solid #ccc' }} />
            ) : (
              <img src={current.url} alt="" className="h-10 w-10 rounded object-cover" />
            )}
            <div>
              <p className="text-xs font-medium text-neutral-800">{current.name}</p>
              {!current.solidColor && (
                <p className="text-[10px] text-neutral-500">
                  {current.tileWidthMm}×{current.tileHeightMm} mm
                </p>
              )}
            </div>
          </div>
          {!current.solidColor && (
            <>
              <div className="flex items-center gap-2 text-[11px] text-neutral-600">
                <span>Layout:</span>
                {(['straight', 'diagonal'] as const).map((l) => (
                  <button
                    key={l}
                    onClick={() => updateCurrent({ layout: l })}
                    className={`rounded px-1.5 py-0.5 capitalize ${current.layout === l ? 'bg-sky-600 text-white' : 'bg-white border border-neutral-300'}`}
                  >
                    {l}
                  </button>
                ))}
              </div>
              <div className="mt-1.5 flex items-center gap-2 text-[11px] text-neutral-600">
                <span>Grout:</span>
                {[2, 3, 5].map((w) => (
                  <button
                    key={w}
                    onClick={() => updateCurrent({ groutWidthMm: w })}
                    className={`rounded px-1.5 py-0.5 ${current.groutWidthMm === w ? 'bg-sky-600 text-white' : 'bg-white border border-neutral-300'}`}
                  >
                    {w}mm
                  </button>
                ))}
                <span className="ml-1 flex gap-1">
                  {GROUT_COLORS.map((c) => (
                    <button
                      key={c}
                      onClick={() => updateCurrent({ groutColor: c })}
                      className={`h-4 w-4 rounded-full border ${current.groutColor === c ? 'ring-2 ring-sky-500' : 'border-neutral-300'}`}
                      style={{ background: c }}
                      title={c}
                    />
                  ))}
                </span>
              </div>
            </>
          )}
        </div>
      )}

      {/* Paint (solid colour) */}
      <div className="mb-2">
        <p className="mb-1 text-[11px] font-semibold text-neutral-600">Paint (solid colour)</p>
        <div className="flex flex-wrap gap-1">
          {PAINT_COLORS.map((c) => (
            <button
              key={c}
              onClick={() => applyPaint(c)}
              className={`h-6 w-6 rounded border ${current?.solidColor === c ? 'ring-2 ring-sky-500' : 'border-neutral-300'}`}
              style={{ background: c }}
              title={c}
            />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-1.5">
        {textures.map((t) => (
          <button
            key={t.id}
            onClick={() => apply(t)}
            className={`overflow-hidden rounded border text-left transition ${current?.textureId === t.id ? 'border-sky-500 ring-2 ring-sky-300' : 'border-neutral-200 hover:border-sky-400'}`}
            title={`${t.name} — ${t.tile_width_mm}×${t.tile_height_mm}mm`}
          >
            {t.preview_url && <img src={t.preview_url} alt={t.name} className="h-14 w-full object-cover" />}
            <p className="truncate px-1 py-0.5 text-[10px] text-neutral-700">{t.name}</p>
          </button>
        ))}
      </div>
      {textures.length === 0 && <p className="text-xs text-neutral-500">No textures in this category.</p>}
    </div>
  );
}

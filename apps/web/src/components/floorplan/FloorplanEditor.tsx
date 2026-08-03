import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDesignStore, DEFAULT_CEILING } from '../../stores/design-store';
import { useEditorStore } from '../../stores/editor-store';
import { roomBounds } from '../../stores/design-store';
import type { WallProfile } from '../../lib/types';

const PROFILE_LABEL: Record<WallProfile, string> = {
  rectangle: 'Rectangle',
  gable: 'Sloped roof',
  stairs: 'Under stairs',
  boxing: 'Boxing (pipes)',
};
const PROFILE_COLOR: Record<WallProfile, string> = {
  rectangle: '#5b6470',
  gable: '#0e7a5f',
  stairs: '#b45309',
  boxing: '#6d28d9',
};

/**
 * 2D floor-plan editor (SVG). In "draw" mode the user clicks the floor outline;
 * the program auto-generates a wall per edge. In "walls" mode the user clicks a
 * wall to edit its shape (rectangle / sloped roof / under stairs / boxing).
 */
export function FloorplanEditor() {
  const room = useDesignStore((s) => s.design.room);
  const mode = useEditorStore((s) => s.mode);
  const selectedWallId = useEditorStore((s) => s.selectedWallId) ?? null;
  const setSelectedWall = useEditorStore((s) => s.setSelectedWall);

  const addWallPoint = useDesignStore((s) => s.addWallPoint);
  const closePolygon = useDesignStore((s) => s.closePolygon);
  const undoPoint = useDesignStore((s) => s.undoPoint);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 900, h: 700 });
  const [cursor, setCursor] = useState<[number, number] | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const pts = room.floorPoints;
  // While the room is open (drawing), keep a stable minimum viewport so the
  // zoom doesn't collapse to a single point (which would map every subsequent
  // click to the same world cell and block further drawing).
  const bounds = useMemo(() => {
    const b = roomBounds(pts);
    const MIN_W = 3000;
    const MIN_D = 2000;
    const w = Math.max(MIN_W, b.maxX - b.minX);
    const d = Math.max(MIN_D, b.maxZ - b.minZ);
    const cx = (b.minX + b.maxX) / 2;
    const cz = (b.minZ + b.maxZ) / 2;
    return { minX: cx - w / 2, maxX: cx + w / 2, minZ: cz - d / 2, maxZ: cz + d / 2, cx, cz };
  }, [pts]);
  const roomW = Math.max(1, bounds.maxX - bounds.minX);
  const roomD = Math.max(1, bounds.maxZ - bounds.minZ);
  const S = Math.min(size.w / roomW, size.h / roomD) * 0.82;
  const cx = bounds.cx;
  const cz = bounds.cz;
  const ox = size.w / 2;
  const oz = size.h / 2;

  const sx = useCallback((x: number) => (x - cx) * S + ox, [S, cx, ox]);
  const sz = useCallback((z: number) => (z - cz) * S + oz, [S, cz, oz]);

  const toWorld = useCallback(
    (e: React.MouseEvent) => {
      const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
      const wx = (e.clientX - rect.left - ox) / S + cx;
      const wz = (e.clientY - rect.top - oz) / S + cz;
      return [wx, wz] as [number, number];
    },
    [S, ox, oz, cx, cz],
  );

  const handleClick = (e: React.MouseEvent) => {
    if (mode === 'draw' && !room.closed) {
      const [wx, wz] = toWorld(e);
      addWallPoint(Math.round(wx / 25) * 25, Math.round(wz / 25) * 25);
    }
  };

  const handleMove = (e: React.MouseEvent) => {
    if (mode === 'draw' && !room.closed) setCursor(toWorld(e));
  };

  // keyboard for draw mode
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const st = useDesignStore.getState();
      if (e.key === 'Escape') {
        if (st.design.room.closed) {
          useEditorStore.getState().setMode('navigate');
        } else {
          st.undoPoint();
        }
      } else if (e.key === 'Enter') {
        st.closePolygon();
        useEditorStore.getState().setMode('walls');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const isWalls = mode === 'walls' || (mode === 'draw' && room.closed);

  return (
    <div ref={wrapRef} className="relative h-full w-full bg-neutral-50">
      <svg
        className="h-full w-full cursor-crosshair"
        style={{ touchAction: 'none' }}
        onClick={handleClick}
        onMouseMove={handleMove}
      >
        {/* grid */}
        {Array.from({ length: Math.ceil(roomW / 250) + 3 }).map((_, i) => {
          const gx = sx(bounds.minX + (i + 1) * 250);
          return <line key={`gx${i}`} x1={gx} y1={0} x2={gx} y2={size.h} stroke="#e5e5e5" strokeWidth={1} />;
        })}
        {Array.from({ length: Math.ceil(roomD / 250) + 3 }).map((_, i) => {
          const gz = sz(bounds.minZ + (i + 1) * 250);
          return <line key={`gz${i}`} x1={0} y1={gz} x2={size.w} y2={gz} stroke="#e5e5e5" strokeWidth={1} />;
        })}

        {/* floor outline (drawn points) */}
        {pts.length > 1 && (
          <polyline
            points={pts.map((p) => `${sx(p[0])},${sz(p[1])}`).join(' ')}
            fill="rgba(56,130,246,0.10)"
            stroke="#3b82f6"
            strokeWidth={2}
            fillRule="evenodd"
          />
        )}
        {/* cursor preview */}
        {mode === 'draw' && !room.closed && pts.length > 0 && cursor && (
          <line x1={sx(pts[pts.length - 1][0])} y1={sz(pts[pts.length - 1][1])} x2={sx(cursor[0])} y2={sz(cursor[1])} stroke="#f59e0b" strokeWidth={2} strokeDasharray="6 4" />
        )}
        {/* floor points */}
        {pts.map((p, i) => (
          <circle key={i} cx={sx(p[0])} cy={sz(p[1])} r={4} fill="#3b82f6" />
        ))}

        {/* walls (edit mode) */}
        {isWalls &&
          room.walls.map((w, wi) => {
            const a = w.outline[0];
            const b = w.outline[Math.max(0, w.outline.length - 1)];
            const sel = w.id === selectedWallId;
            const col = sel ? '#f59e0b' : PROFILE_COLOR[w.profile];
            const thickness = Math.max(6, (w.thickness || 100) * S * 0.12);
            return (
              <g
                key={w.id}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedWall(w.id);
                }}
                style={{ cursor: 'pointer' }}
              >
                <line x1={sx(a[0])} y1={sz(a[1])} x2={sx(b[0])} y2={sz(b[1])} stroke={col} strokeWidth={thickness} strokeLinecap="butt" opacity={sel ? 1 : 0.55} />
                <line x1={sx(a[0])} y1={sz(a[1])} x2={sx(b[0])} y2={sz(b[1])} stroke="#fff" strokeWidth={thickness * 0.35} />
                <title>{`Wall ${wi + 1} — ${PROFILE_LABEL[w.profile]} · ${Math.round(Math.hypot(b[0] - a[0], b[1] - a[1]))}mm`}</title>
              </g>
            );
          })}
      </svg>

      {/* hint bar */}
      <div className="pointer-events-none absolute bottom-0 left-1/2 z-10 -translate-x-1/2 mb-3 whitespace-nowrap rounded-full bg-black/70 px-4 py-1.5 text-xs text-white">
        {room.closed
          ? `Room drawn — ${room.walls.length} wall${room.walls.length === 1 ? '' : 's'}. Click a wall to edit its shape.`
          : 'Draw the floor outline — click to place points, Enter/Esc to finish'}
      </div>

      {room.closed && (
        <div className="absolute left-4 top-4 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs shadow-sm">
          <div className="mb-1 font-semibold text-neutral-700">Walls ({room.walls.length})</div>
          {room.walls.map((w, i) => (
            <div
              key={w.id}
              onClick={() => setSelectedWall(w.id)}
              className={`mb-0.5 cursor-pointer rounded px-1.5 py-0.5 ${w.id === selectedWallId ? 'bg-amber-100 text-amber-900' : 'text-neutral-600 hover:bg-neutral-100'}`}
            >
              <span>{i + 1}.</span> <span style={{ color: PROFILE_COLOR[w.profile] }}>●</span> {PROFILE_LABEL[w.profile]}
            </div>
          ))}
        </div>
      )}

      {!room.closed && (
        <button
          onClick={() => {
            closePolygon();
            useEditorStore.getState().setMode('walls');
          }}
          className="absolute bottom-20 left-1/2 z-20 -translate-x-1/2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-emerald-700"
        >
          ✓ Finish room ({room.floorPoints.length} points)
        </button>
      )}
    </div>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDesignStore } from '../../stores/design-store';
import { useEditorStore } from '../../stores/editor-store';
import { roomBounds } from '../../stores/design-store';
import { buildWalls, cornerAnglesDeg, distToSegment, polygonCentroid } from '../../lib/geometry';

/**
 * 2D floor-plan editor (SVG). While the room is open ("draw") the user clicks
 * the floor outline; clicking the FIRST point (once ≥3 points exist) encloses
 * the room. Once closed, corner points can be dragged to reshape the room and
 * right-clicking on a wall inserts a new corner point.
 */
export function FloorplanEditor() {
  const room = useDesignStore((s) => s.design.room);
  const mode = useEditorStore((s) => s.mode);

  const addWallPoint = useDesignStore((s) => s.addWallPoint);
  const closePolygon = useDesignStore((s) => s.closePolygon);
  const undoPoint = useDesignStore((s) => s.undoPoint);
  const startDrawing = useDesignStore((s) => s.startDrawing);
  const moveCorner = useDesignStore((s) => s.moveCorner);
  const addCornerOnWall = useDesignStore((s) => s.addCornerOnWall);
  const removeCorner = useDesignStore((s) => s.removeCorner);
  const beginEdit = useDesignStore((s) => s.beginEdit);
  const commitEdit = useDesignStore((s) => s.commitEdit);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 900, h: 700 });
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [nearFirst, setNearFirst] = useState(false);
  const dragRef = useRef<number | null>(null);

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
  const closed = room.closed;
  const drawing = mode === 'draw' && !closed;

  // While the room is open (drawing), keep a stable minimum viewport so the
  // zoom doesn't collapse to a single point.
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
    (e: { clientX: number; clientY: number }) => {
      const rect = wrapRef.current!.getBoundingClientRect();
      const wx = (e.clientX - rect.left - ox) / S + cx;
      const wz = (e.clientY - rect.top - oz) / S + cz;
      return [wx, wz] as [number, number];
    },
    [S, ox, oz, cx, cz],
  );

  const closeIfOnFirst = useCallback(
    (wx: number, wz: number) => {
      if (pts.length >= 3) {
        const f = pts[0];
        if (Math.hypot(wx - f[0], wz - f[1]) < 120) {
          closePolygon();
          useEditorStore.getState().setMode('walls');
          return true;
        }
      }
      return false;
    },
    [pts, closePolygon],
  );

  const handleClick = (e: React.MouseEvent) => {
    if (!drawing) return;
    const [wx, wz] = toWorld(e);
    if (closeIfOnFirst(wx, wz)) return;
    addWallPoint(Math.round(wx / 25) * 25, Math.round(wz / 25) * 25);
  };

  const handleMove = (e: React.MouseEvent) => {
    if (drawing) {
      const [wx, wz] = toWorld(e);
      setCursor([wx, wz]);
      setNearFirst(pts.length >= 3 && Math.hypot(wx - pts[0][0], wz - pts[0][1]) < 120);
    }
  };

  // corner dragging (closed room)
  const onCornerDown = (e: React.PointerEvent, index: number) => {
    e.stopPropagation();
    e.preventDefault();
    beginEdit();
    dragRef.current = index;
    const move = (ev: PointerEvent) => {
      if (dragRef.current == null) return;
      const [wx, wz] = toWorld(ev);
      moveCorner(dragRef.current, Math.round(wx / 25) * 25, Math.round(wz / 25) * 25);
    };
    const up = () => {
      dragRef.current = null;
      commitEdit();
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  // right-click a wall to insert a corner point
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    if (!closed) return;
    const [wx, wz] = toWorld(e);
    const n = pts.length;
    let best = -1;
    let bestDPx = 12; // px threshold
    for (let i = 0; i < n; i++) {
      const a = pts[i];
      const b = pts[(i + 1) % n];
      const d = distToSegment(wx, wz, a[0], a[1], b[0], b[1]);
      // skip near the ends — the corner handles already cover those
      const dx = b[0] - a[0], dz = b[1] - a[1];
      const len2 = dx * dx + dz * dz || 1;
      const t = ((wx - a[0]) * dx + (wz - a[1]) * dz) / len2;
      if (t < 0.08 || t > 0.92) continue;
      const dPx = d * S;
      if (dPx < bestDPx) {
        best = i;
        bestDPx = dPx;
      }
    }
    if (best >= 0) addCornerOnWall(best, wx, wz);
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

  const first = pts[0];

  // corner angles (visual only) + wall lengths for the closed room
  const angles = useMemo(() => (closed && pts.length >= 3 ? cornerAnglesDeg(pts) : []), [closed, pts]);
  const wallSegs = useMemo(() => (closed && pts.length >= 3 ? buildWalls(pts) : []), [closed, pts]);
  const centroid = useMemo(() => (pts.length >= 3 ? polygonCentroid(pts) : ([0, 0] as [number, number])), [pts]);

  return (
    <div ref={wrapRef} className="relative h-full w-full bg-neutral-50">
      <svg
        className="h-full w-full cursor-crosshair"
        style={{ touchAction: 'none' }}
        onClick={handleClick}
        onMouseMove={handleMove}
        onContextMenu={handleContextMenu}
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
        {drawing && pts.length > 0 && cursor && (
          <line
            x1={sx(pts[pts.length - 1][0])}
            y1={sz(pts[pts.length - 1][1])}
            x2={sx(cursor[0])}
            y2={sz(cursor[1])}
            stroke="#f59e0b"
            strokeWidth={2}
            strokeDasharray="6 4"
          />
        )}

        {/* floor points */}
        {drawing &&
          pts.map((p, i) => {
            const isFirst = i === 0 && nearFirst;
            return (
              <circle
                key={i}
                cx={sx(p[0])}
                cy={sz(p[1])}
                r={isFirst ? 9 : 5}
                fill={isFirst ? '#f59e0b' : '#3b82f6'}
                stroke={isFirst ? '#fff' : 'none'}
                strokeWidth={2}
              />
            );
          })}

        {/* closed room: draggable corner handles — double-click deletes one */}
        {closed &&
          pts.map((p, i) => (
            <g
              key={i}
              style={{ cursor: 'grab' }}
              onPointerDown={(e) => onCornerDown(e, i)}
              onDoubleClick={(e) => {
                e.stopPropagation();
                removeCorner(i);
              }}
            >
              <circle cx={sx(p[0])} cy={sz(p[1])} r={8} fill="#fff" stroke="#3b82f6" strokeWidth={2} />
              <circle cx={sx(p[0])} cy={sz(p[1])} r={3.5} fill="#3b82f6" />
            </g>
          ))}

        {/* corner angle labels (visual only, closed room) */}
        {closed &&
          pts.length >= 3 &&
          pts.map((p, i) => {
            // nudge the label slightly toward the polygon centre
            const dx = centroid[0] - p[0];
            const dz = centroid[1] - p[1];
            const d = Math.hypot(dx, dz) || 1;
            const lx = sx(p[0] + (dx / d) * 260);
            const lz = sz(p[1] + (dz / d) * 260);
            return (
              <text
                key={`ang${i}`}
                x={lx}
                y={lz}
                fontSize={10}
                fill="#9ca3af"
                textAnchor="middle"
                dominantBaseline="middle"
                className="select-none"
              >
                {Math.round(angles[i])}°
              </text>
            );
          })}

        {/* wall length labels (closed room) */}
        {closed &&
          wallSegs.map((w) => (
            <text
              key={`len${w.index}`}
              x={sx(w.a[0] + w.u[0] * (w.length / 2) + w.n[0] * 140)}
              y={sz(w.a[1] + w.u[1] * (w.length / 2) + w.n[1] * 140)}
              fontSize={10}
              fill="#6b7280"
              textAnchor="middle"
              dominantBaseline="middle"
              className="select-none"
            >
              {Math.round(w.length)} mm
            </text>
          ))}

        {closed && (
          <text x={12} y={18} fontSize={11} fill="#6b7280" className="select-none">
            Drag a corner to reshape · double-click a corner to delete it · right-click a wall to add a corner · set exact lengths in the left panel
          </text>
        )}
      </svg>

      {/* hint bar */}
      <div className="pointer-events-none absolute bottom-0 left-1/2 z-10 -translate-x-1/2 mb-3 whitespace-nowrap rounded-full bg-black/70 px-4 py-1.5 text-xs text-white">
        {drawing
          ? pts.length >= 3
            ? 'Click the first point to close the room'
            : 'Draw the floor outline — click to place points'
          : `Room drawn — ${room.walls.length} wall${room.walls.length === 1 ? '' : 's'}. Drag corners to reshape, or go to Edit Walls for the 3D view.`}
      </div>

      {!closed && (
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

      {closed && (
        <button
          onClick={startDrawing}
          className="absolute right-4 top-4 z-20 rounded-lg border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 shadow-sm hover:bg-neutral-50"
          title="Clear the outline and draw a new one"
        >
          ✏️ Redraw
        </button>
      )}

      {first && nearFirst && drawing && (
        <div className="pointer-events-none absolute left-1/2 top-6 z-10 -translate-x-1/2 rounded-full bg-amber-500 px-3 py-1 text-xs font-medium text-white shadow">
          Click to close the room
        </div>
      )}
    </div>
  );
}

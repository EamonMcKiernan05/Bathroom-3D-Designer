import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Scene } from '../components/viewport/Scene';
import { Toolbar, ModeHint } from '../components/ui/Toolbar';
import { LeftPanel, RightPanel } from '../components/ui/Panels';
import { CatalogueBrowser } from '../components/catalogue/CatalogueBrowser';
import { TexturePicker } from '../components/surfaces/TexturePicker';
import { useDesignStore } from '../stores/design-store';
import { useEditorStore } from '../stores/editor-store';
import { api } from '../lib/api';
import { buildWalls, polygonCentroid } from '../lib/geometry';
import { makeItemFromProduct } from '../components/viewport/Scene';
import type { Product, SavedDesign } from '../lib/types';

export function EditorPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const designIdParam = params.get('design');

  const [exportOpen, setExportOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [bottomTab, setBottomTab] = useState<'catalogue' | 'surfaces'>('catalogue');
  const [surfaceCat, setSurfaceCat] = useState('wall-tiles');
  const sceneWrapRef = useRef<HTMLDivElement>(null);

  const showNotice = useCallback((msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(''), 2500);
  }, []);

  // load design from ?design=ID
  useEffect(() => {
    if (!designIdParam) return;
    api
      .getDesign(Number(designIdParam))
      .then((d: SavedDesign) => {
        useDesignStore.getState().loadDesign(d.data, d.name);
        useDesignStore.getState().setDesignId(d.id);
        useDesignStore.getState().setDesignName(d.name);
      })
      .catch(() => showNotice('Failed to load design'));
  }, [designIdParam, showNotice]);

  const save = useCallback(async () => {
    setSaving(true);
    try {
      const st = useDesignStore.getState();
      const payload = { name: st.designName || 'Untitled Design', data: st.design };
      let id = st.designId;
      if (id) {
        await api.updateDesign(id, { name: payload.name, data: payload.data });
      } else {
        const created = await api.createDesign(payload);
        id = created.id;
        st.setDesignId(id);
      }
      st.setSavedAt(new Date().toLocaleTimeString());
      showNotice(`Saved as design #${id}`);
    } catch (e) {
      showNotice(`Save failed: ${String(e).slice(0, 120)}`);
    } finally {
      setSaving(false);
    }
  }, [showNotice]);

  // keyboard shortcuts (page level)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = e.target as unknown;
      const typing = tag instanceof Element ? tag.closest('input,textarea,select') : null;
      const st = useDesignStore.getState();
      const ed = useEditorStore.getState();
      if (typing) return;
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        save();
      } else if ((e.ctrlKey || e.metaKey) && e.key === 'z' && e.shiftKey) {
        e.preventDefault();
        st.redo();
      } else if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        st.undo();
      } else if (e.key === 'Escape') {
        if (ed.mode === 'draw') {
          ed.setMode('navigate');
          useDesignStore.getState().selectItem(null);
        } else {
          useDesignStore.getState().selectItem(null);
          useDesignStore.getState().selectSurface(null);
        }
      } else if (e.key === '1') ed.setMode('navigate');
      else if (e.key === '2') ed.setMode('draw');
      else if (e.key === '3') ed.setMode('place');
      else if (e.key === 'g') ed.toggleGrid();
      else if (e.key === '/') ed.setCameraMode(ed.cameraMode === '3d' ? '2d' : '3d');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [save]);

  const newDesign = useCallback(() => {
    if (!confirm('Start a new design? Unsaved changes will be lost.')) return;
    useDesignStore.getState().resetDesign();
    navigate('/editor');
  }, [navigate]);

  const addFromCatalogue = useCallback((p: Product) => {
    // place at room center, offset per item
    const st = useDesignStore.getState();
    const pts = st.design.room.floorPoints;
    const [cx, cz] = polygonCentroid(pts);
    const item = makeItemFromProduct(p, cx, cz);
    st.addItem(item);
    st.selectItem(item.id);
    useEditorStore.setState({ mode: 'place' });
    showNotice(`${p.name} added — drag it into position`);
  }, [showNotice]);

  const exportFloorplan = useCallback(() => {
    const st = useDesignStore.getState();
    const pts = st.design.room.floorPoints;
    if (pts.length < 3) return;
    const walls = buildWalls(pts);
    const scale = 3; // px per mm
    const pad = 80;
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    for (const [x, z] of pts) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minZ = Math.min(minZ, z); maxZ = Math.max(maxZ, z);
    }
    const w = (maxX - minX) * scale + pad * 2;
    const h = (maxZ - minZ) * scale + pad * 2;
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, w, h);
    const px = (x: number) => pad + (x - minX) * scale;
    const pz = (z: number) => pad + (z - minZ) * scale;
    // items footprints
    for (const it of st.design.items) {
      const dw = (it.widthMm ?? 400) / 2;
      const dd = (it.depthMm ?? 400) / 2;
      ctx.save();
      ctx.translate(px(it.position[0]), pz(it.position[2]));
      ctx.rotate(-it.rotation);
      ctx.fillStyle = 'rgba(56,130,246,0.35)';
      ctx.strokeStyle = '#2563eb';
      ctx.lineWidth = 1.5;
      ctx.fillRect(-dw * scale, -dd * scale, dw * 2 * scale, dd * 2 * scale);
      ctx.strokeRect(-dw * scale, -dd * scale, dw * 2 * scale, dd * 2 * scale);
      ctx.restore();
    }
    // walls
    ctx.strokeStyle = '#1f2937';
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.moveTo(px(pts[0][0]), pz(pts[0][1]));
    for (let i = 1; i < pts.length; i++) ctx.lineTo(px(pts[i][0]), pz(pts[i][1]));
    ctx.closePath();
    ctx.stroke();
    // openings
    for (const d of st.design.doors) {
      const wall = walls[d.wallIndex];
      if (!wall) continue;
      const cx2 = wall.a[0] + wall.u[0] * d.pos;
      const cz2 = wall.a[1] + wall.u[1] * d.pos;
      ctx.strokeStyle = '#b45309';
      ctx.lineWidth = 4;
      ctx.beginPath();
      const wx = px(cx2), wz = pz(cz2);
      ctx.moveTo(wx - (d.width / 2) * scale, wz);
      ctx.lineTo(wx + (d.width / 2) * scale, wz);
      ctx.stroke();
    }
    // dimension labels
    ctx.fillStyle = '#374151';
    ctx.font = '12px sans-serif';
    for (const wall of walls) {
      const mx = px(wall.a[0] + wall.u[0] * (wall.length / 2));
      const mz = pz(wall.a[1] + wall.u[1] * (wall.length / 2));
      ctx.fillText(`${Math.round(wall.length)}mm`, mx - 20, mz - 8);
    }
    const a = document.createElement('a');
    a.download = 'floorplan.png';
    a.href = canvas.toDataURL('image/png');
    a.click();
    showNotice('Floorplan PNG exported');
  }, [showNotice]);

  const mode = useEditorStore((s) => s.mode);
  const drawPointCount = useDesignStore((s) => s.design.room.floorPoints.length);
  const closePolygon = useDesignStore((s) => s.closePolygon);

  return (
    <div className="flex h-screen flex-col bg-neutral-100">
      <Toolbar onSave={save} onExport={() => setExportOpen(true)} onNew={newDesign} />
      <div className="flex min-h-0 flex-1">
        <LeftPanel />
        <div className="relative min-w-0 flex-1" ref={sceneWrapRef}>
          <Scene />
          <ModeHint />
          {notice && (
            <div className="absolute left-1/2 top-3 z-20 -translate-x-1/2 rounded-lg bg-neutral-900 px-4 py-2 text-xs text-white shadow-lg">
              {notice}
            </div>
          )}
          {mode === 'draw' && (
            <button
              onClick={() => closePolygon()}
              className="absolute bottom-20 left-1/2 z-20 -translate-x-1/2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-emerald-700"
            >
              ✓ Finish room ({drawPointCount} points)
            </button>
          )}
        </div>
        <RightPanel />
      </div>

      {/* bottom panel */}
      <div className="h-52 border-t border-neutral-200 bg-white">
        <div className="flex items-center gap-1 border-b border-neutral-200 px-2">
          <button
            onClick={() => setBottomTab('catalogue')}
            className={`px-3 py-1.5 text-xs font-medium ${bottomTab === 'catalogue' ? 'border-b-2 border-sky-600 text-sky-700' : 'text-neutral-500'}`}
          >
            🛒 Catalogue
          </button>
          <button
            onClick={() => setBottomTab('surfaces')}
            className={`px-3 py-1.5 text-xs font-medium ${bottomTab === 'surfaces' ? 'border-b-2 border-sky-600 text-sky-700' : 'text-neutral-500'}`}
          >
            🧱 Surfaces & Tiles
          </button>
          {bottomTab === 'surfaces' && (
            <div className="ml-2 flex gap-1">
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
          <span className="ml-auto text-[10px] text-neutral-400">Shortcuts: 1 navigate · 2 draw · 3 place · R rotate · Del delete · Ctrl+Z undo · Ctrl+S save</span>
        </div>
        <div className="h-[calc(100%-33px)]">
          {bottomTab === 'catalogue' ? <CatalogueBrowser onAddToDesign={addFromCatalogue} /> : <TexturePicker category={surfaceCat} />}
        </div>
      </div>

      {exportOpen && <ExportDialog onClose={() => setExportOpen(false)} onExportFloorplan={exportFloorplan} />}
    </div>
  );
}

function ExportDialog({ onClose, onExportFloorplan }: { onClose: () => void; onExportFloorplan: () => void }) {
  const [bom, setBom] = useState<{ items: { product_name: string; retailer_name: string; sku: string; unit_price?: number; total_price?: number; retailer_url?: string; finish?: string }[]; grand_total?: number; design_name: string } | null>(null);
  const [err, setErr] = useState('');
  const designId = useDesignStore((s) => s.designId);
  const designName = useDesignStore((s) => s.designName);

  useEffect(() => {
    if (!designId) {
      setErr('Save the design first to generate a bill of materials.');
      return;
    }
    api.bom(designId).then(setBom).catch((e) => setErr(String(e).slice(0, 200)));
  }, [designId]);

  const copyList = () => {
    if (!bom) return;
    const lines = bom.items.map((i) => `• ${i.product_name} — ${i.retailer_name} — £${(i.unit_price ?? 0).toFixed(2)}`);
    navigator.clipboard.writeText(lines.join('\n'));
    alert('Shopping list copied to clipboard');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="max-h-[80vh] w-[640px] overflow-y-auto rounded-xl bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-bold text-neutral-900">Export — {designName}</h2>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-700">✕</button>
        </div>
        {err && <p className="mb-2 rounded bg-amber-50 p-2 text-xs text-amber-700">{err}</p>}
        {bom && (
          <>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-200 text-left text-neutral-500">
                  <th className="py-1 pr-2">Product</th>
                  <th className="py-1 pr-2">Retailer</th>
                  <th className="py-1 pr-2">SKU</th>
                  <th className="py-1 pr-2 text-right">Price</th>
                  <th className="py-1 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {bom.items.map((i, idx) => (
                  <tr key={idx} className="border-b border-neutral-100">
                    <td className="py-1.5 pr-2 text-neutral-800">{i.product_name}</td>
                    <td className="py-1.5 pr-2 text-neutral-500">{i.retailer_name}</td>
                    <td className="py-1.5 pr-2 font-mono text-neutral-500">{i.sku}</td>
                    <td className="py-1.5 pr-2 text-right text-neutral-700">{i.unit_price != null ? `£${i.unit_price.toFixed(2)}` : '—'}</td>
                    <td className="py-1.5 text-right font-medium text-neutral-900">{i.total_price != null ? `£${i.total_price.toFixed(2)}` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-3 flex items-center justify-between">
              <span className="text-sm font-bold text-neutral-900">Grand total: £{(bom.grand_total ?? 0).toFixed(2)}</span>
              <div className="flex gap-2">
                <button onClick={copyList} className="rounded border border-neutral-300 px-3 py-1.5 text-xs text-neutral-700 hover:bg-neutral-50">
                  Copy list
                </button>
                {designId && (
                  <a href={api.bomCsvUrl(designId)} className="rounded border border-neutral-300 px-3 py-1.5 text-xs text-neutral-700 hover:bg-neutral-50">
                    Download CSV
                  </a>
                )}
                <button onClick={onExportFloorplan} className="rounded border border-neutral-300 px-3 py-1.5 text-xs text-neutral-700 hover:bg-neutral-50">
                  2D Floorplan PNG
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import type { SavedDesign } from '../lib/types';

export function DesignsPage() {
  const [designs, setDesigns] = useState<SavedDesign[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = useCallback(() => {
    api.designs().then(setDesigns).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const remove = async (id: number) => {
    if (!confirm('Delete this design?')) return;
    await api.deleteDesign(id);
    load();
  };

  return (
    <div className="min-h-screen bg-neutral-100 px-6 py-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-neutral-900">My designs</h1>
          <Link to="/editor" className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700">
            + New design
          </Link>
        </div>
        {loading && <p className="text-sm text-neutral-500">Loading…</p>}
        {!loading && designs.length === 0 && (
          <div className="rounded-xl border border-dashed border-neutral-300 bg-white p-10 text-center">
            <p className="text-neutral-500">No saved designs yet.</p>
            <Link to="/editor" className="mt-2 inline-block text-sm text-sky-600 hover:underline">
              Create your first design →
            </Link>
          </div>
        )}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {designs.map((d) => (
            <div key={d.id} className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
              {d.thumbnail_url ? (
                <img src={d.thumbnail_url} alt="" className="h-32 w-full object-cover" />
              ) : (
                <div className="flex h-32 items-center justify-center bg-gradient-to-br from-sky-100 to-white text-3xl">🛁</div>
              )}
              <div className="p-3">
                <p className="truncate text-sm font-semibold text-neutral-900">{d.name}</p>
                <p className="text-[11px] text-neutral-400">
                  {(d.data?.items?.length ?? 0)} items · updated {d.updated_at ? new Date(d.updated_at).toLocaleString() : '—'}
                </p>
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() => navigate(`/editor?design=${d.id}`)}
                    className="flex-1 rounded bg-sky-600 px-2 py-1 text-xs font-medium text-white hover:bg-sky-700"
                  >
                    Open in editor
                  </button>
                  <button
                    onClick={() => navigate(`/designs/${d.id}`)}
                    className="flex-1 rounded border border-neutral-300 px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-50"
                  >
                    View 3D
                  </button>
                  <button onClick={() => remove(d.id)} className="rounded border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50">
                    🗑
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-8">
          <Link to="/" className="text-sm text-neutral-500 hover:underline">
            ← Back home
          </Link>
        </div>
      </div>
    </div>
  );
}

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../lib/api';
import { useEditorStore } from '../../stores/editor-store';
import type { Product } from '../../lib/types';

interface Props {
  onAddToDesign: (p: Product) => void;
}

export function CatalogueBrowser({ onAddToDesign }: Props) {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<{ slug: string; name: string; depth: number; product_count: number }[]>([]);
  const [cat, setCat] = useState('');
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.categories().then(setCategories).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const page = await api.products({ category: cat || undefined, q: q || undefined, per_page: 60, sort: 'name' });
      setProducts(page.items);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [cat, q]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  const grouped = useMemo(() => {
    const g: Record<string, Product[]> = {};
    for (const p of products) {
      const key = p.category?.split('/')[1] ?? 'other';
      (g[key] ??= []).push(p);
    }
    return g;
  }, [products]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-neutral-200 px-3 py-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search products…"
          className="w-56 rounded border border-neutral-300 px-2 py-1 text-sm outline-none focus:border-sky-500"
        />
        <select
          value={cat}
          onChange={(e) => setCat(e.target.value)}
          className="rounded border border-neutral-300 px-2 py-1 text-sm"
        >
          <option value="">All categories</option>
          {categories
            .filter((c) => c.depth === 1)
            .map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name} ({c.product_count})
              </option>
            ))}
        </select>
        <span className="ml-auto text-xs text-neutral-500">{products.length} products</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {error && <p className="text-sm text-red-600">{error}</p>}
        {loading && <p className="text-sm text-neutral-500">Loading…</p>}
        {!loading && !error && Object.entries(grouped).map(([key, items]) => (
          <div key={key} className="mb-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">{key}</h4>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6 xl:grid-cols-8">
              {items.map((p) => (
                <ProductCard key={p.id} product={p} onAddToDesign={onAddToDesign} />
              ))}
            </div>
          </div>
        ))}
        {!loading && !error && products.length === 0 && <p className="text-sm text-neutral-500">No products found.</p>}
      </div>
    </div>
  );
}

function ProductCard({ product, onAddToDesign }: { product: Product; onAddToDesign: (p: Product) => void }) {
  const setDragProduct = useEditorStore((s) => s.setDragProduct);
  return (
    <div
      className="group cursor-grab rounded-lg border border-neutral-200 bg-white p-2 shadow-sm transition hover:border-sky-400 hover:shadow"
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData('application/product', JSON.stringify(product));
        e.dataTransfer.effectAllowed = 'copy';
        setDragProduct(product);
      }}
      onDragEnd={() => setDragProduct(null)}
      title="Drag into the room, or click to add"
    >
      <div className="relative mb-1 h-16 overflow-hidden rounded bg-neutral-50">
        {product.thumbnail_url ? (
          <img src={product.thumbnail_url} alt={product.name} className="h-full w-full object-contain" draggable={false} />
        ) : (
          <div className="flex h-full items-center justify-center text-2xl">🛁</div>
        )}
        {product.model_status !== 'ready' && (
          <span className="absolute bottom-0 left-0 rounded-tr bg-amber-500 px-1 text-[9px] text-white">model pending</span>
        )}
      </div>
      <p className="line-clamp-2 text-[11px] leading-tight text-neutral-700" title={product.name}>
        {product.name}
      </p>
      <div className="mt-1 flex items-center justify-between">
        <span className="text-xs font-semibold text-neutral-900">
          {product.price_gbp != null ? `£${Number(product.price_gbp).toFixed(2)}` : '—'}
        </span>
        {product.retailer_slug && <span className="text-[9px] text-neutral-400">{product.retailer_slug}</span>}
      </div>
      <button
        onClick={() => onAddToDesign(product)}
        className="mt-1.5 w-full rounded bg-sky-600 px-1 py-0.5 text-[11px] font-medium text-white opacity-0 transition group-hover:opacity-100 hover:bg-sky-700"
      >
        + Add to room
      </button>
    </div>
  );
}

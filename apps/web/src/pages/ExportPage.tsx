import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../lib/api';
import type { BomResponse } from '../lib/types';

export function ExportPage() {
  const { id } = useParams();
  const [bom, setBom] = useState<BomResponse | null>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api.bom(Number(id)).then(setBom).catch((e) => setErr(String(e)));
  }, [id]);

  if (err) return <div className="p-8 text-red-600">{err}</div>;
  if (!bom) return <div className="p-8 text-neutral-500">Loading…</div>;

  const byRetailer: Record<string, typeof bom.items> = {};
  for (const it of bom.items) (byRetailer[it.retailer_name] ??= []).push(it);

  return (
    <div className="min-h-screen bg-neutral-100 px-6 py-8">
      <div className="mx-auto max-w-3xl">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-neutral-900">{bom.design_name} — Bill of Materials</h1>
            <p className="text-xs text-neutral-500">
              Generated {new Date(bom.generated_at).toLocaleString()} · prices are demo values, always verify with retailer
            </p>
          </div>
          <div className="flex gap-2">
            <a href={api.bomCsvUrl(bom.design_id)} className="rounded-lg border border-neutral-300 bg-white px-4 py-2 text-sm hover:bg-neutral-50">
              ⬇ CSV
            </a>
            <Link to={`/designs/${bom.design_id}`} className="rounded-lg bg-neutral-800 px-4 py-2 text-sm text-white hover:bg-neutral-900">
              ← Back to design
            </Link>
          </div>
        </div>
        {Object.entries(byRetailer).map(([retailer, items]) => (
          <div key={retailer} className="mb-4 overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
            <div className="border-b border-neutral-200 bg-neutral-50 px-4 py-2 text-sm font-semibold text-neutral-700">{retailer}</div>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-100 text-left text-neutral-400">
                  <th className="px-4 py-1.5">Product</th>
                  <th className="px-2 py-1.5">SKU</th>
                  <th className="px-2 py-1.5">Finish</th>
                  <th className="px-2 py-1.5 text-right">Unit</th>
                  <th className="px-4 py-1.5 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it, i) => (
                  <tr key={i} className="border-b border-neutral-50">
                    <td className="px-4 py-2 text-neutral-800">
                      {it.product_name}
                      {it.retailer_url && (
                        <a href={it.retailer_url} target="_blank" rel="noreferrer" className="ml-1 text-sky-600 hover:underline">
                          ↗
                        </a>
                      )}
                    </td>
                    <td className="px-2 py-2 font-mono text-neutral-500">{it.sku}</td>
                    <td className="px-2 py-2 text-neutral-500">{it.finish ?? '—'}</td>
                    <td className="px-2 py-2 text-right text-neutral-700">{it.unit_price != null ? `£${it.unit_price.toFixed(2)}` : '—'}</td>
                    <td className="px-4 py-2 text-right font-medium text-neutral-900">{it.total_price != null ? `£${it.total_price.toFixed(2)}` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
        <div className="rounded-xl border border-neutral-300 bg-white p-4 text-right shadow-sm">
          <span className="text-sm text-neutral-500">Grand total: </span>
          <span className="text-xl font-bold text-neutral-900">£{(bom.grand_total ?? 0).toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}

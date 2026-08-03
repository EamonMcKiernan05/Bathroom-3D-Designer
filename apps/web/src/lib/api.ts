// API client — talks to the FastAPI backend (proxied by Vite)

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 300)}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  products: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') qs.set(k, String(v));
    const q = qs.toString();
    return req<Page<any>>(`/api/v1/products${q ? `?${q}` : ''}`);
  },
  categories: () => req<any[]>('/api/v1/categories'),
  retailers: () => req<any[]>('/api/v1/retailers'),
  textures: (category?: string) =>
    req<any[]>(`/api/v1/textures${category ? `?category=${category}` : ''}`),
  designs: () => req<any[]>('/api/v1/designs'),
  getDesign: (id: number) => req<any>(`/api/v1/designs/${id}`),
  createDesign: (payload: { name: string; description?: string; data: unknown }) =>
    req<any>('/api/v1/designs', { method: 'POST', body: JSON.stringify(payload) }),
  updateDesign: (id: number, payload: { name?: string; data?: unknown; thumbnail_url?: string }) =>
    req<any>(`/api/v1/designs/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteDesign: (id: number) => req<void>(`/api/v1/designs/${id}`, { method: 'DELETE' }),
  bom: (id: number) => req<any>(`/api/v1/designs/${id}/bom`),
  bomCsvUrl: (id: number) => `/api/v1/designs/${id}/bom.csv`,
  share: (id: number) => req<any>(`/api/v1/designs/${id}/share`, { method: 'POST' }),
  uploadPlanPhoto: async (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/v1/plans/from-photo', { method: 'POST', body: fd });
    if (!res.ok) {
      const t = await res.text().catch(() => '');
      throw new Error(`${res.status}: ${t.slice(0, 220)}`);
    }
    return res.json();
  },
};

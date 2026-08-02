import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import { api } from '../lib/api';
import { Room } from '../components/viewport/Room';
import { PlacedProduct } from '../components/viewport/PlacedProduct';
import type { SavedDesign } from '../lib/types';

/** Read-only 3D view of a saved design (share-link style). */
export function DesignViewPage() {
  const { id } = useParams();
  const [design, setDesign] = useState<SavedDesign | null>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api.getDesign(Number(id)).then(setDesign).catch((e) => setErr(String(e)));
  }, [id]);

  if (err) return <div className="p-8 text-red-600">{err}</div>;
  if (!design) return <div className="p-8 text-neutral-500">Loading design…</div>;

  const d = design.data;
  const pts = d.room?.floorPoints ?? [[-1200, -900], [1200, -900], [1200, 900], [-1200, 900]];
  const xs = pts.map((p) => p[0]);
  const zs = pts.map((p) => p[1]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const cz = (Math.min(...zs) + Math.max(...zs)) / 2;
  const diag = Math.max(2000, Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs)));

  return (
    <div className="flex h-screen flex-col bg-neutral-900">
      <div className="flex items-center justify-between border-b border-neutral-700 px-4 py-2">
        <div>
          <span className="text-sm font-semibold text-white">{design.name}</span>
          <span className="ml-2 text-[11px] text-neutral-400">read-only view</span>
        </div>
        <div className="flex items-center gap-2">
          <Link to={`/designs/${id}/bom`} className="rounded bg-neutral-700 px-3 py-1 text-xs text-white hover:bg-neutral-600">
            Bill of materials
          </Link>
          <Link to={`/editor?design=${id}`} className="rounded bg-sky-600 px-3 py-1 text-xs font-medium text-white hover:bg-sky-700">
            Edit this design
          </Link>
        </div>
      </div>
      <div className="relative flex-1">
        <Canvas
          gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
          camera={{ position: [cx + diag * 0.9, diag * 0.8, cz + diag * 0.9], fov: 50 }}
        >
          <ambientLight intensity={1.0} />
          <directionalLight position={[3000, 6000, 2000]} intensity={1.2} />
          <directionalLight position={[-3000, 5000, -2000]} intensity={0.7} />
          <PerspectiveCamera makeDefault position={[cx + diag * 0.9, diag * 0.8, cz + diag * 0.9]} fov={50} near={10} far={100000} />
          <OrbitControls makeDefault target={[cx, 1000, cz]} maxPolarAngle={Math.PI / 2 - 0.02} minDistance={300} maxDistance={30000} />
          <Room />
          {d.items?.map((item) => (
            <PlacedProduct key={item.id} item={item} />
          ))}
          <gridHelper args={[Math.max(8000, diag * 1.6), Math.max(160, (diag * 1.6) / 50), '#555', '#333']} position={[cx, 0.5, cz]} />
        </Canvas>
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-black/60 px-4 py-1 text-[11px] text-neutral-300">
          Drag to orbit · scroll to zoom
        </div>
      </div>
    </div>
  );
}

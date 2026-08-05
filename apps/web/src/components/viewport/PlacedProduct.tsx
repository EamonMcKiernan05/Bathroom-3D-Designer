import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { useGLTF, useCursor } from '@react-three/drei';
import type { ThreeEvent } from '@react-three/fiber';
import { useDesignStore } from '../../stores/design-store';
import type { PlacedItem } from '../../lib/types';

/**
 * Loads a GLB (metre scale from Blender) and renders it at mm scale (×1000).
 * Model origin convention: back-bottom-center, front faces +Z at rotation 0.
 */
export function PlacedProduct({
  item,
  onBoundsReady,
  onDragStart,
}: {
  item: PlacedItem;
  onBoundsReady?: (id: string, b: { w: number; h: number; d: number } | null) => void;
  onDragStart?: (id: string, e: ThreeEvent<PointerEvent>) => void;
}) {
  const gltf = item.modelUrl ? useGLTF(item.modelUrl) : null;
  const selectItem = useDesignStore((s) => s.selectItem);
  const selectedId = useDesignStore((s) => s.selectedItemId);
  const colliding = useDesignStore((s) => s.collisionMap[item.id] ?? false);

  const isSelected = selectedId === item.id;
  const [hovered, setHovered] = useState(false);
  useCursor(hovered, 'grab');

  const scene = useMemo(() => {
    if (!gltf) return null;
    return gltf.scene.clone(true);
  }, [gltf]);

  const bounds = useMemo(() => {
    if (!scene) return null;
    const box = new THREE.Box3().setFromObject(scene);
    const size = box.getSize(new THREE.Vector3());
    return { w: size.x * 1000, h: size.y * 1000, d: size.z * 1000 };
  }, [scene]);

  useEffect(() => {
    onBoundsReady?.(item.id, bounds);
    return () => onBoundsReady?.(item.id, null);
  }, [item.id, bounds, onBoundsReady]);

  const scale = item.scale || 1000;

  if (item.visible === false) return null;

  return (
    <group
      position={item.position}
      rotation={[0, item.rotation, 0]}
      userData={{ itemId: item.id }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={() => setHovered(false)}
      onPointerDown={(e) => onDragStart?.(item.id, e)}
      onClick={(e) => {
        e.stopPropagation();
        selectItem(item.id);
      }}
    >
      {scene ? (
        <primitive object={scene} scale={scale} />
      ) : (
        <mesh>
          <boxGeometry args={[(item.widthMm ?? 400), (item.heightMm ?? 400), (item.depthMm ?? 400)]} />
          <meshStandardMaterial color="#cbd5e1" />
        </mesh>
      )}

      {/* selection outline */}
      {isSelected && bounds && (
        <mesh position={[0, bounds.h / 2, 0]}>
          <boxGeometry args={[bounds.w + 10, bounds.h + 10, bounds.d + 10]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.3} depthWrite={false} />
        </mesh>
      )}

      {/* collision warning */}
      {colliding && (
        <mesh position={[0, (bounds?.h ?? 400) / 2, 0]}>
          <boxGeometry args={[(bounds?.w ?? 400) + 8, (bounds?.h ?? 400) + 8, (bounds?.d ?? 400) + 8]} />
          <meshBasicMaterial color="#ef4444" transparent opacity={0.35} depthWrite={false} />
        </mesh>
      )}
    </group>
  );
}

/**
 * Collision detection for all placed items, in mm (XZ footprints, rotation-aware).
 */
export function useCollisions(items: PlacedItem[], boundsByItem: Record<string, { w: number; h: number; d: number } | null>) {
  return useMemo(() => {
    const map: Record<string, boolean> = {};
    const boxes = items.map((it) => {
      const b = boundsByItem[it.id];
      const w = (b?.w ?? it.widthMm ?? 400) / 2;
      const d = (b?.d ?? it.depthMm ?? 400) / 2;
      const cos = Math.cos(it.rotation);
      const sin = Math.sin(it.rotation);
      const rx = Math.abs(w * cos) + Math.abs(d * sin);
      const rz = Math.abs(w * sin) + Math.abs(d * cos);
      return { id: it.id, x: it.position[0], z: it.position[2], rx, rz };
    });
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i], b = boxes[j];
        const overlap = Math.abs(a.x - b.x) < a.rx + b.rx && Math.abs(a.z - b.z) < a.rz + b.rz;
        if (overlap) {
          map[a.id] = true;
          map[b.id] = true;
        }
      }
    }
    return map;
  }, [items, boundsByItem]);
}

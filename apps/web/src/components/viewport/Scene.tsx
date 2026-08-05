import { useMemo, useRef, useState, useCallback, useEffect } from 'react';
import * as THREE from 'three';
import { Canvas, useThree, type ThreeEvent } from '@react-three/fiber';
import { OrbitControls, OrthographicCamera, PerspectiveCamera, Html } from '@react-three/drei';
import { Room } from './Room';
import { PlacedProduct, useCollisions } from './PlacedProduct';
import { buildWalls, clampPointToPolygon, distToSegment, snapToWall } from '../../lib/geometry';
import { useDesignStore, roomBounds } from '../../stores/design-store';
import { useEditorStore, mountHeightFor, isWallMounted } from '../../stores/editor-store';
import type { PlacedItem, Product } from '../../lib/types';

function raycastToPlane(clientX: number, clientY: number, y: number, camera: THREE.Camera, el: HTMLElement): THREE.Vector3 | null {
  const rect = el.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((clientX - rect.left) / rect.width) * 2 - 1,
    -((clientY - rect.top) / rect.height) * 2 + 1,
  );
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(ndc, camera);
  const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -y);
  const hit = new THREE.Vector3();
  if (raycaster.ray.intersectPlane(plane, hit)) return hit;
  return null;
}

export function makeItemFromProduct(p: Product, x: number, z: number): PlacedItem {
  const wallMounted = isWallMounted(p.category);
  const mount = wallMounted ? mountHeightFor(p.category) : 0;
  return {
    id: crypto.randomUUID(),
    productId: p.id,
    name: p.name,
    category: p.category ?? '',
    price: p.price_gbp ?? null,
    retailerName: p.retailer_name,
    retailerUrl: p.retailer_website,
    sku: p.retailer_sku,
    finish: p.finishes?.[0],
    position: [x, mount, z],
    rotation: 0,
    scale: (p.model_scale ?? 1) * 1000,
    modelUrl: p.model_url,
    wallMounted,
    mountHeight: mount,
    widthMm: p.width_mm ?? undefined,
    heightMm: p.height_mm ?? undefined,
    depthMm: p.depth_mm ?? undefined,
  };
}

function SceneContents() {
  const design = useDesignStore((s) => s.design);
  const selectedItemId = useDesignStore((s) => s.selectedItemId);
  const selectItem = useDesignStore((s) => s.selectItem);
  const addItem = useDesignStore((s) => s.addItem);
  const moveItem = useDesignStore((s) => s.moveItem);
  const addOpening = useDesignStore((s) => s.addOpening);
  const setCollisionMap = useDesignStore((s) => s.setCollisionMap);
  const selectSurface = useDesignStore((s) => s.selectSurface);

  const mode = useEditorStore((s) => s.mode);
  const cameraMode = useEditorStore((s) => s.cameraMode);
  const showGrid = useEditorStore((s) => s.showGrid);
  const showDimensions = useEditorStore((s) => s.showDimensions);
  const snapEnabled = useEditorStore((s) => s.snapEnabled);
  const dragProduct = useEditorStore((s) => s.dragProduct);
  const measure = useEditorStore((s) => s.measure);
  const setMeasurePoint = useEditorStore((s) => s.setMeasurePoint);
  const clearMeasure = useEditorStore((s) => s.clearMeasure);

  const { camera, gl, controls } = useThree();
  const camControls = (controls ?? null) as { enabled: boolean } | null;
  const glEl = gl.domElement;

  const [cursor, setCursor] = useState<THREE.Vector3 | null>(null);
  const [dragGap, setDragGap] = useState<number | null>(null);
  const openingType = useEditorStore((s) => s.openingType);
  const dragRef = useRef<{ id: string } | null>(null);
  const justDraggedRef = useRef(false);

  const room = design.room;
  const walls = useMemo(() => (room.closed ? buildWalls(room.floorPoints) : []), [room.floorPoints, room.closed]);
  const bounds = useMemo(() => roomBounds(room.floorPoints), [room.floorPoints]);

  // item bounds (for collision + selection boxes), fed back by PlacedProduct
  const [itemBounds, setItemBounds] = useState<Record<string, { w: number; h: number; d: number } | null>>({});
  const onBoundsReady = useCallback((id: string, b: { w: number; h: number; d: number } | null) => {
    setItemBounds((prev) => (prev[id] === b ? prev : { ...prev, [id]: b }));
  }, []);
  const collisionMap = useCollisions(design.items, itemBounds);
  useEffect(() => {
    setCollisionMap(collisionMap);
  }, [collisionMap, setCollisionMap]);

  const handlePointerMove = useCallback(
    (e: ThreeEvent<PointerEvent>) => {
      if (mode === 'draw') {
        const hit = raycastToPlane(e.clientX, e.clientY, 0, camera, glEl);
        setCursor(hit);
        return;
      }
      setCursor(null);
      // item dragging is handled by the window-level onDragMove handler
      if (dragGap !== null && !dragStateRef.current) setDragGap(null);
    },
    [camera, glEl, mode, dragGap],
  );

  const handlePointerDown = useCallback(
    (e: ThreeEvent<PointerEvent>) => {
      if (e.button !== 0) return;
      const itemId = (e.object as THREE.Object3D).userData?.itemId as string | undefined;
      if (itemId) {
        e.stopPropagation();
        selectItem(itemId);
        dragRef.current = { id: itemId };
        if (camControls) camControls.enabled = false; // stop orbit fighting the drag
      }
    },
    [selectItem, camControls],
  );

  /** Window-level drag: pointer events are tracked on the window (not via R3F
   *  routing), so the drag keeps working even when the pointer leaves the
   *  canvas or hovers other objects. */
  const dragStateRef = useRef<{ id: string; y: number } | null>(null);

  const onDragMove = useCallback(
    (ev: PointerEvent) => {
      const st = dragStateRef.current;
      if (!st) return;
      const designNow = useDesignStore.getState().design;
      const item = designNow.items.find((i) => i.id === st.id);
      if (!item) return;
      const p = raycastToPlane(ev.clientX, ev.clientY, st.y, camera, glEl);
      if (!p) return;
      const roomNow = designNow.room;
      const ws = roomNow.closed ? buildWalls(roomNow.floorPoints) : [];
      // live gap to nearest wall (in mm) while dragging
      let gap = Infinity;
      for (const w of ws) gap = Math.min(gap, distToSegment(p.x, p.z, w.a[0], w.a[1], w.b[0], w.b[1]));
      setDragGap(Math.round(gap));
      let x = p.x, z = p.z;
      if (snapEnabled) {
        const snap = snapToWall(x, z, roomNow.floorPoints, 150);
        if (snap) {
          useDesignStore.getState().updateItem(item.id, { position: [snap.pos[0], st.y, snap.pos[2]], rotation: snap.rotation });
          setDragGap(0);
          return;
        }
      }
      [x, z] = clampPointToPolygon(x, z, roomNow.floorPoints);
      x = Math.round(x / 50) * 50;
      z = Math.round(z / 50) * 50;
      moveItem(item.id, [x, st.y, z]);
    },
    [camera, glEl, snapEnabled, moveItem],
  );

  /** Begin dragging an item — called from PlacedProduct's onPointerDown so the
   *  drag starts on the ITEM itself (the floor plane never sees the item's
   *  userData, which is why dragging previously did nothing). */
  const startDrag = useCallback(
    (itemId: string, e: ThreeEvent<PointerEvent>) => {
      if (e.button !== 0) return;
      e.stopPropagation(); // keep the floor plane from treating this as a floor click
      selectItem(itemId);
      const item = design.items.find((i) => i.id === itemId);
      dragStateRef.current = { id: itemId, y: item?.position[1] ?? 0 };
      dragRef.current = { id: itemId };
      justDraggedRef.current = false;
      if (camControls) camControls.enabled = false; // stop orbit fighting the drag
      window.addEventListener('pointermove', onDragMove);
    },
    [selectItem, camControls, design.items, onDragMove],
  );

  const endDrag = useCallback(() => {
    if (dragStateRef.current) {
      justDraggedRef.current = true;
      window.removeEventListener('pointermove', onDragMove);
    }
    dragStateRef.current = null;
    dragRef.current = null;
    if (camControls) camControls.enabled = true;
    setDragGap(null);
  }, [camControls, onDragMove]);

  // safety net: pointer released anywhere ends the drag
  useEffect(() => {
    const onUp = () => endDrag();
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointermove', onDragMove);
    };
  }, [endDrag, onDragMove]);

  const handlePointerUp = useCallback(() => {
    endDrag();
  }, [endDrag]);

  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      if (dragRef.current) return;
      // a click synthesized right after an item drag must not act on the floor
      if (justDraggedRef.current) {
        justDraggedRef.current = false;
        return;
      }
      const obj = e.object as THREE.Object3D;
      const surf = obj.userData?.surface as string | undefined;
      const itemId = obj.userData?.itemId as string | undefined;

      if (mode === 'draw' && surf === 'floor') {
        const p = e.point;
        useDesignStore.getState().addWallPoint(Math.round(p.x / 25) * 25, Math.round(p.z / 25) * 25);
        return;
      }
      if (mode === 'place' && surf === 'floor' && dragProduct) {
        const p = e.point;
        const prod = dragProduct as Product;
        const item = makeItemFromProduct(prod, Math.round(p.x / 50) * 50, Math.round(p.z / 50) * 50);
        addItem(item);
        useEditorStore.setState({ dragProduct: null });
        return;
      }
      if (mode === 'openings' && surf === 'wall') {
        const wallIndex = obj.userData?.wallIndex as number;
        const wall = walls[wallIndex];
        if (!wall) return;
        const relX = (e.point.x - wall.a[0]) * wall.u[0] + (e.point.z - wall.a[1]) * wall.u[1];
        const pos = Math.max(50, Math.min(wall.length - 50, relX));
        const isDoor = openingType === 'door';
        addOpening({
          id: crypto.randomUUID(),
          type: openingType,
          wallIndex,
          pos,
          width: isDoor ? 900 : 1200,
          height: isDoor ? 2100 : 1200,
          sillHeight: isDoor ? 0 : 900,
        });
        return;
      }
      if (mode === 'surfaces' && surf) {
        selectSurface({ type: surf as 'floor' | 'ceiling' | 'wall', index: (obj.userData?.wallIndex as number) ?? 0 });
        return;
      }
      if (mode === 'measure' && surf === 'floor') {
        setMeasurePoint([Math.round(e.point.x), Math.round(e.point.z)]);
        return;
      }
      if (itemId) {
        selectItem(itemId);
      } else if (!surf) {
        selectItem(null);
      }
    },
    [mode, dragProduct, walls, openingType, addOpening, addItem, selectItem, selectSurface],
  );

  const handleContextMenu = useCallback((e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    if (mode === 'draw') useDesignStore.getState().undoPoint();
  }, [mode]);

  // keyboard: delete / rotate selected
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const st = useDesignStore.getState();
      const sel = st.selectedItemId;
      if (!sel) return;
      const tag = e.target as unknown;
      const typing = tag instanceof Element ? tag.closest('input,textarea,select') : null;
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (typing) return;
        e.preventDefault();
        st.removeItem(sel);
      } else if ((e.key === 'r' || e.key === 'R') && !typing) {
        const item = st.design.items.find((i) => i.id === sel);
        if (item) st.rotateItem(sel, (item.rotation + Math.PI / 2) % (Math.PI * 2));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const roomCx = Number.isFinite(bounds.cx) ? bounds.cx : 0;
  const roomCz = Number.isFinite(bounds.cz) ? bounds.cz : 0;

  // dev hook: expose world->screen projection + item world positions so
  // automated tests can aim CDP pointer events precisely.
  useEffect(() => {
    (window as unknown as Record<string, unknown>).__bathroom3d = {
      projectToScreen: (wx: number, wy: number, wz: number) => {
        const v = new THREE.Vector3(wx, wy, wz).project(camera);
        const rect = glEl.getBoundingClientRect();
        return {
          x: rect.left + ((v.x + 1) / 2) * rect.width,
          y: rect.top + ((1 - v.y) / 2) * rect.height,
        };
      },
      itemPositions: () =>
        useDesignStore.getState().design.items.map((i) => ({
          productId: i.productId,
          id: i.id,
          pos: i.position,
        })),
      /** What does a ray from the camera through this screen point hit? */
      raycastAt: (clientX: number, clientY: number) => {
        const rect = glEl.getBoundingClientRect();
        const ndc = new THREE.Vector2(
          ((clientX - rect.left) / rect.width) * 2 - 1,
          -((clientY - rect.top) / rect.height) * 2 + 1,
        );
        const ray = new THREE.Raycaster();
        ray.setFromCamera(ndc, camera);
        const root = camera.parent;
        if (!root) return { error: 'no scene root' };
        const hits = ray.intersectObjects(root.children, true);
        return hits.slice(0, 6).map((h) => ({
          dist: Math.round(h.distance),
          point: [Math.round(h.point.x), Math.round(h.point.y), Math.round(h.point.z)],
          userData: h.object.userData,
          objName: h.object.name,
        }));
      },
    };
    return () => {
      delete (window as unknown as Record<string, unknown>).__bathroom3d;
    };
  }, [camera, glEl]);
  const roomDiag = Math.max(2000, Math.min(30000, Math.hypot(bounds.maxX - bounds.minX, bounds.maxZ - bounds.minZ)));
  const gridSize = Math.min(Math.max(8000, roomDiag * 1.6), 50000);

  return (
    <>
      {/* lights — fully lit, no shadows */}
      <ambientLight intensity={1.0} />
      <directionalLight position={[3000, 6000, 2000]} intensity={1.2} />
      <directionalLight position={[-3000, 5000, -2000]} intensity={0.7} />
      <directionalLight position={[0, 4000, 5000]} intensity={0.5} />

      {cameraMode === '2d' ? (
        <OrthographicCamera makeDefault position={[roomCx, 6000, roomCz]} zoom={0.45} near={-20000} far={30000} />
      ) : (
        <PerspectiveCamera makeDefault position={[roomCx + roomDiag * 0.9, roomDiag * 0.8, roomCz + roomDiag * 0.9]} fov={50} near={10} far={100000} />
      )}
      <OrbitControls
        makeDefault
        target={[roomCx, 1000, roomCz]}
        enableRotate={cameraMode !== '2d'}
        enableZoom
        enablePan
        minDistance={300}
        maxDistance={30000}
        maxPolarAngle={Math.PI / 2 - 0.02}
      />

      <Room />

      {design.items.map((item) => (
        <PlacedProduct key={item.id} item={item} onBoundsReady={onBoundsReady} onDragStart={startDrag} />
      ))}

      {showGrid && (
        <gridHelper args={[gridSize, gridSize / 50, '#8a8a8a', '#c6c6c6']} position={[roomCx, 0.5, roomCz]} />
      )}

      {/* cursor preview in draw mode */}
      {mode === 'draw' && cursor && room.floorPoints.length > 0 && (
        <line>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              args={[new Float32Array([
                room.floorPoints[room.floorPoints.length - 1][0], 1, room.floorPoints[room.floorPoints.length - 1][1],
                cursor.x, 1, cursor.z,
              ]), 3]}
            />
          </bufferGeometry>
          <lineBasicMaterial color="#f59e0b" />
        </line>
      )}

      {/* dimension labels */}
      {showDimensions &&
        room.closed &&
        walls.map((w) => (
          <Html
            key={`dim-${w.index}`}
            position={[w.a[0] + w.u[0] * (w.length / 2) + w.n[0] * 250, 120, w.a[1] + w.u[1] * (w.length / 2) + w.n[1] * 250]}
            center
            style={{ pointerEvents: 'none' }}
          >
            <div
              style={{
                background: 'rgba(255,255,255,0.92)',
                padding: '1px 6px',
                borderRadius: 4,
                fontSize: 11,
                color: '#444',
                whiteSpace: 'nowrap',
                border: '1px solid #ddd',
              }}
            >
              {Math.round(w.length)} mm
            </div>
          </Html>
        ))}

      {/* measurement tool overlay */}
      {mode === 'measure' && measure && (
        <group>
          <mesh position={[measure.a[0], 1, measure.a[1]]}>
            <sphereGeometry args={[45, 12, 8]} />
            <meshBasicMaterial color="#f59e0b" />
          </mesh>
          {measure.b && (
            <>
              <mesh position={[measure.b[0], 1, measure.b[1]]}>
                <sphereGeometry args={[45, 12, 8]} />
                <meshBasicMaterial color="#f59e0b" />
              </mesh>
              <line>
                <bufferGeometry>
                  <bufferAttribute
                    attach="attributes-position"
                    args={[new Float32Array([measure.a[0], 1, measure.a[1], measure.b[0], 1, measure.b[1]]), 3]}
                  />
                </bufferGeometry>
                <lineBasicMaterial color="#f59e0b" />
              </line>
              <Html
                position={[(measure.a[0] + measure.b[0]) / 2, 120, (measure.a[1] + measure.b[1]) / 2]}
                center
                style={{ pointerEvents: 'none' }}
              >
                <div style={{ background: '#f59e0b', color: '#fff', padding: '2px 7px', borderRadius: 6, fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
                  {Math.round(Math.hypot(measure.a[0] - measure.b[0], measure.a[1] - measure.b[1]))} mm
                </div>
              </Html>
            </>
          )}
        </group>
      )}

      {/* live gap-to-wall while dragging an item */}
      {dragGap !== null &&
        selectedItemId &&
        (() => {
          const it = design.items.find((i) => i.id === selectedItemId);
          if (!it) return null;
          return (
            <Html position={[it.position[0], (it.position[1] || 0) + 250, it.position[2]]} center style={{ pointerEvents: 'none' }}>
              <div style={{ background: '#111827', color: '#fff', padding: '2px 7px', borderRadius: 6, fontSize: 11, whiteSpace: 'nowrap' }}>
                {dragGap === 0 ? 'snapped to wall' : `${dragGap} mm to wall`}
              </div>
            </Html>
          );
        })()}

      {/* transparent interaction plane: draws walls / places items / moves selected */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[roomCx, 0, roomCz]}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
        userData={{ surface: 'floor' }}
      >
        <planeGeometry args={[gridSize, gridSize]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>
    </>
  );
}

export function Scene() {
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const raw = e.dataTransfer.getData('application/product');
    if (!raw) return;
    const prod = JSON.parse(raw) as Product;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    useEditorStore.setState({ dragProduct: prod });
    window.dispatchEvent(new CustomEvent('bathroom:drop', { detail: { x, y, product: prod } }));
  }, []);

  return (
    <div className="relative h-full w-full" onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
      <Canvas
        shadows={false}
        dpr={[1, 2]}
        gl={{ antialias: true, preserveDrawingBuffer: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.0 }}
        camera={{ position: [2500, 3000, 3500], fov: 50 }}
      >
        <SceneContents />
        <DropHandler />
      </Canvas>
    </div>
  );
}

/** Bridges HTML5 drag-drop (catalogue -> canvas) into a 3D floor placement. */
function DropHandler() {
  const { camera, gl } = useThree();
  const addItem = useDesignStore((s) => s.addItem);
  useEffect(() => {
    const onDropEvent = (e: Event) => {
      const detail = (e as CustomEvent).detail as { x: number; y: number; product: Product };
      if (!detail) return;
      const el = gl.domElement;
      const rect = el.getBoundingClientRect();
      const clientX = rect.left + ((detail.x + 1) / 2) * rect.width;
      const clientY = rect.top + ((-detail.y + 1) / 2) * rect.height;
      const hit = raycastToPlane(clientX, clientY, 0, camera, el);
      if (!hit) return;
      const st = useDesignStore.getState();
      const pts = st.design.room.floorPoints;
      const [cx, cz] = clampPointToPolygon(hit.x, hit.z, pts);
      const item = makeItemFromProduct(detail.product, Math.round(cx / 50) * 50, Math.round(cz / 50) * 50);
      addItem(item);
      useEditorStore.setState({ dragProduct: null });
    };
    window.addEventListener('bathroom:drop', onDropEvent);
    return () => window.removeEventListener('bathroom:drop', onDropEvent);
  }, [camera, gl, addItem]);
  return null;
}

import * as THREE from 'three';
import type { TextureAssignment } from './types';

/**
 * World-space tile UVs: uv = localPosition / tileSize.
 * With wrapS/T = RepeatWrapping and repeat = (1,1), the texture tiles at exact
 * real-world scale (1 unit = 1mm). No texture.repeat math needed per surface.
 */

export function tilePlaneUVs(
  geom: THREE.BufferGeometry,
  width: number,
  height: number,
  tileW: number,
  tileH: number,
): void {
  const pos = geom.attributes.position as THREE.BufferAttribute;
  const count = pos.count;
  const uv = new Float32Array(count * 2);
  const w = Math.max(1, tileW);
  const h = Math.max(1, tileH);
  for (let i = 0; i < count; i++) {
    uv[i * 2] = (pos.getX(i) + width / 2) / w;
    uv[i * 2 + 1] = (pos.getY(i) + height / 2) / h;
  }
  geom.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
}

export function tileShapeUVs(
  geom: THREE.BufferGeometry,
  minX: number,
  minZ: number,
  tileW: number,
  tileH: number,
): void {
  const pos = geom.attributes.position as THREE.BufferAttribute;
  const count = pos.count;
  const uv = new Float32Array(count * 2);
  const w = Math.max(1, tileW);
  const h = Math.max(1, tileH);
  for (let i = 0; i < count; i++) {
    uv[i * 2] = (pos.getX(i) - minX) / w;
    uv[i * 2 + 1] = (pos.getZ(i) - minZ) / h;
  }
  geom.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
}

export function configureTextureMaterial(
  material: THREE.MeshStandardMaterial,
  texture: THREE.Texture,
  assignment: TextureAssignment,
): void {
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(1, 1);
  texture.colorSpace = THREE.SRGBColorSpace;
  if (assignment.layout === 'diagonal') {
    texture.rotation = Math.PI / 4;
    texture.center.set(0.5, 0.5);
  } else {
    texture.rotation = assignment.rotation * (Math.PI / 180);
    texture.center.set(0.5, 0.5);
  }
  texture.needsUpdate = true;
  material.map = texture;
  material.needsUpdate = true;
}

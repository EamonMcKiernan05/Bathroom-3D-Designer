// Shared domain types — all dimensions in MILLIMETRES (1 unit = 1mm in Three.js)

export interface Product {
  id: number;
  name: string;
  brand?: string;
  category?: string;
  price_gbp?: number;
  price_note?: string;
  width_mm?: number;
  height_mm?: number;
  depth_mm?: number;
  finishes: string[];
  colours: string[];
  variant_data: Record<string, unknown>;
  model_url?: string;
  model_status: string;
  main_image_url?: string;
  thumbnail_url?: string;
  retailer_name?: string;
  retailer_slug?: string;
  retailer_website?: string;
  retailer_sku?: string;
  model_scale?: number;
  placeholder_kind?: string;
}

export interface TextureInfo {
  id: number;
  slug: string;
  name: string;
  category: string;
  tile_width_mm: number;
  tile_height_mm: number;
  thickness_mm?: number;
  colour_family?: string;
  finish?: string;
  material?: string;
  pattern?: string;
  albedo_url?: string;
  normal_url?: string;
  roughness_url?: string;
  preview_url?: string;
}

export interface WallOpening {
  id: string;
  type: 'door' | 'window';
  wallIndex: number;
  /** position along the wall in mm (center of opening, from segment start) */
  pos: number;
  width: number;
  height: number;
  /** window only: sill height from floor */
  sillHeight: number;
}

export interface PlacedItem {
  id: string;
  productId: number;
  name: string;
  category: string;
  price: number | null;
  retailerName?: string;
  retailerUrl?: string;
  sku?: string;
  finish?: string;
  position: [number, number, number];
  rotation: number; // radians about Y
  scale: number; // mm multiplier applied to the metre-scale GLB (1000)
  modelUrl?: string;
  wallMounted: boolean;
  mountHeight: number; // mm from floor for wall-mounted items
  widthMm?: number;
  heightMm?: number;
  depthMm?: number;
  visible?: boolean;
}

export interface TextureAssignment {
  textureId: number;
  tileWidthMm: number;
  tileHeightMm: number;
  groutWidthMm: number;
  groutColor: string;
  layout: 'straight' | 'diagonal';
  rotation: number;
  url: string;
  name: string;
  /** Flat paint colour (no texture). When set, the surface is a solid colour. */
  solidColor?: string;
}

export interface RoomState {
  floorPoints: [number, number][];
  ceilingHeight: number;
  wallThickness: number;
  closed: boolean;
}

export interface DesignData {
  room: RoomState;
  doors: WallOpening[];
  windows: WallOpening[];
  items: PlacedItem[];
  floorTexture: TextureAssignment | null;
  wallTextures: Record<number, TextureAssignment>;
  ceilingTexture: TextureAssignment | null;
  version: number;
}

export interface SavedDesign {
  id: number;
  name: string;
  description?: string;
  data: DesignData;
  thumbnail_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface BomItem {
  product_name: string;
  retailer_name: string;
  retailer_url?: string;
  sku: string;
  finish?: string;
  quantity: number;
  unit_price?: number;
  total_price?: number;
}

export interface BomResponse {
  design_id: number;
  design_name: string;
  items: BomItem[];
  grand_total?: number;
  generated_at: string;
}

import type { GridMeta } from "./schemas";

/**
 * Reconstruct 0.01 degree grid-cell geometry from grid_meta + row/col
 * (spec §5.0 / §6). SW corner = (lat0 + row*cell_deg, lon0 + col*cell_deg);
 * cell spans one cell_deg east and north. Returns GeoJSON [lon, lat] order.
 */

export function cellRing(meta: GridMeta, row: number, col: number): [number, number][] {
  const lat = meta.lat0 + row * meta.cell_deg;
  const lon = meta.lon0 + col * meta.cell_deg;
  const d = meta.cell_deg;
  return [
    [lon, lat],
    [lon + d, lat],
    [lon + d, lat + d],
    [lon, lat + d],
    [lon, lat],
  ];
}

export function cellCentroid(meta: GridMeta, row: number, col: number): [number, number] {
  return [
    meta.lon0 + (col + 0.5) * meta.cell_deg,
    meta.lat0 + (row + 0.5) * meta.cell_deg,
  ];
}

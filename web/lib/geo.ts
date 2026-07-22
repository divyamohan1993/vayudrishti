import type { Feature, FeatureCollection, Geometry, Position } from "geojson";
import type { WardProperties } from "./schemas";

export type WardFC = FeatureCollection<Geometry, WardProperties>;
export type WardFeature = Feature<Geometry, WardProperties>;

export type Bounds = [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]

/** Bounds over an entire FeatureCollection (Polygon / MultiPolygon). */
export function featureBounds(fc: WardFC): Bounds {
  let minLon = Infinity,
    minLat = Infinity,
    maxLon = -Infinity,
    maxLat = -Infinity;
  const visit = (pos: Position) => {
    const [lon, lat] = pos;
    if (lon < minLon) minLon = lon;
    if (lat < minLat) minLat = lat;
    if (lon > maxLon) maxLon = lon;
    if (lat > maxLat) maxLat = lat;
  };
  for (const f of fc.features) walkCoords(f.geometry, visit);
  return [minLon, minLat, maxLon, maxLat];
}

function walkCoords(geom: Geometry, visit: (p: Position) => void) {
  switch (geom.type) {
    case "Polygon":
      geom.coordinates.forEach((ring) => ring.forEach(visit));
      break;
    case "MultiPolygon":
      geom.coordinates.forEach((poly) => poly.forEach((ring) => ring.forEach(visit)));
      break;
    default:
      break;
  }
}

export interface Projector {
  project: (lon: number, lat: number) => [number, number];
  width: number;
  height: number;
}

/**
 * Local equirectangular projector fit to bounds, longitude compressed by
 * cos(midLat) so the city is not horizontally stretched. Y flipped for SVG.
 */
export function makeProjector(
  bounds: Bounds,
  targetW: number,
  targetH: number,
  padding = 8,
): Projector {
  const [minLon, minLat, maxLon, maxLat] = bounds;
  const midLat = (minLat + maxLat) / 2;
  const kx = Math.cos((midLat * Math.PI) / 180);
  const w = (maxLon - minLon) * kx || 1e-6;
  const h = maxLat - minLat || 1e-6;
  const availW = targetW - padding * 2;
  const availH = targetH - padding * 2;
  const scale = Math.min(availW / w, availH / h);
  const drawW = w * scale;
  const drawH = h * scale;
  const offX = padding + (availW - drawW) / 2;
  const offY = padding + (availH - drawH) / 2;
  return {
    width: targetW,
    height: targetH,
    project: (lon, lat) => [
      offX + (lon - minLon) * kx * scale,
      offY + (maxLat - lat) * scale,
    ],
  };
}

/** SVG path data for a Polygon / MultiPolygon (closed) or LineString (open). */
export function geometryToPath(geom: Geometry, p: Projector): string {
  const toPath = (coords: Position[], close: boolean) => {
    let d = "";
    coords.forEach((pos, i) => {
      const [x, y] = p.project(pos[0], pos[1]);
      d += `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    });
    return close ? `${d}Z` : d;
  };
  switch (geom.type) {
    case "Polygon":
      return geom.coordinates.map((r) => toPath(r, true)).join("");
    case "MultiPolygon":
      return geom.coordinates.map((poly) => poly.map((r) => toPath(r, true)).join("")).join("");
    case "LineString":
      return toPath(geom.coordinates, false);
    case "MultiLineString":
      return geom.coordinates.map((l) => toPath(l, false)).join("");
    default:
      return "";
  }
}

/** Centroid of a geometry's outer rings (rough, for label placement). */
export function geometryCentroid(geom: Geometry): [number, number] | null {
  let sx = 0,
    sy = 0,
    n = 0;
  const add = (pos: Position) => {
    sx += pos[0];
    sy += pos[1];
    n++;
  };
  walkCoords(geom, add);
  return n ? [sx / n, sy / n] : null;
}

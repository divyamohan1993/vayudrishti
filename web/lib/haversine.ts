/**
 * Client-side nearest-city match for the location-aware entry (spec §6,
 * acceptance 14). Runs entirely on-device against manifest centroids; the
 * browser coordinates are NEVER sent anywhere (no network call in this path).
 */

export interface LatLon {
  lat: number;
  lon: number;
}

const R_KM = 6371;

export function haversineKm(a: LatLon, b: LatLon): number {
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLon = ((b.lon - a.lon) * Math.PI) / 180;
  const la1 = (a.lat * Math.PI) / 180;
  const la2 = (b.lat * Math.PI) / 180;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(la1) * Math.cos(la2) * Math.sin(dLon / 2) ** 2;
  return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

export interface NearestResult<T> {
  city: T;
  distanceKm: number;
}

/** Nearest city by great-circle distance to its centroid. */
export function nearestCity<T extends { centroid: LatLon }>(
  point: LatLon,
  cities: readonly T[],
): NearestResult<T> | null {
  let best: NearestResult<T> | null = null;
  for (const city of cities) {
    const distanceKm = haversineKm(point, city.centroid);
    if (!best || distanceKm < best.distanceKm) best = { city, distanceKm };
  }
  return best;
}

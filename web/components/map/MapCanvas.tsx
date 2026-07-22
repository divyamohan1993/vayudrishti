"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer } from "@deck.gl/layers";
import type { Layer } from "@deck.gl/core";
import type { WardFC } from "@/lib/geo";
import type { WardView } from "@/lib/wardView";
import { AQI_RGB } from "@/lib/aqi";
import type { SatelliteLayer } from "@/lib/store";

/**
 * WebGL2 map: MapLibre GL canvas + deck.gl ward choropleth + toggleable NASA
 * GIBS satellite raster overlays (zero-auth). Dynamically imported (ssr:false)
 * so the map vendor chunk is async and off the initial bundle (A7). No street
 * basemap tiles: a dark data-canvas, policy-clean, GIBS the only remote tiles.
 */

const GIBS_HOST = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";
const GIBS_LAYERS: Record<Exclude<SatelliteLayer, "off">, { id: string; fmt: string; level: number; opacity: number }> = {
  no2: { id: "OMI_Nitrogen_Dioxide_Tropospheric_Column", fmt: "png", level: 6, opacity: 0.8 },
  aod: { id: "MODIS_Combined_Value_Added_AOD", fmt: "png", level: 6, opacity: 0.8 },
  viirs: { id: "VIIRS_SNPP_CorrectedReflectance_TrueColor", fmt: "jpg", level: 9, opacity: 0.92 },
};

function gibsDateDaysAgo(days: number): string {
  const d = new Date(Date.now() - days * 86_400_000);
  return d.toISOString().slice(0, 10);
}

function gibsTiles(layer: Exclude<SatelliteLayer, "off">): { url: string; maxzoom: number } {
  const l = GIBS_LAYERS[layer];
  const date = gibsDateDaysAgo(layer === "viirs" ? 1 : 2);
  return {
    url: `${GIBS_HOST}/${l.id}/default/${date}/GoogleMapsCompatible_Level${l.level}/{z}/{y}/{x}.${l.fmt}`,
    maxzoom: l.level,
  };
}

export default function MapCanvas({
  fc,
  roads,
  viewById,
  bbox,
  satellite,
  selectedWard,
  onHover,
  onSelect,
}: {
  fc: WardFC;
  roads?: WardFC;
  viewById: Map<string, WardView>;
  bbox: [number, number, number, number];
  satellite: SatelliteLayer;
  selectedWard: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  // Latest values for imperative handlers without re-creating the map.
  const state = useRef({ viewById, satellite, selectedWard, roads, onHover, onSelect });
  state.current = { viewById, satellite, selectedWard, roads, onHover, onSelect };

  // Create map once.
  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#050b0d" } }] },
      bounds: [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      fitBoundsOptions: { padding: 24 },
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: "NASA GIBS" }), "bottom-left");
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay);
    mapRef.current = map;
    overlayRef.current = overlay;

    map.on("load", () => {
      updateOverlay();
      updateGibs();
    });

    return () => {
      overlay.finalize?.();
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function updateOverlay() {
    const overlay = overlayRef.current;
    if (!overlay) return;
    const { viewById: vb, satellite: sat, selectedWard: sel } = state.current;
    const fillAlpha = sat === "off" ? 190 : 55;
    const layer = new GeoJsonLayer<{ ward_id: string }>({
      id: "wards",
      data: fc as unknown as GeoJSON.FeatureCollection,
      pickable: true,
      stroked: true,
      filled: true,
      getFillColor: (f) => {
        const v = vb.get((f.properties as { ward_id: string }).ward_id);
        if (!v) return [20, 40, 48, 120];
        const [r, g, b] = AQI_RGB[v.category];
        return [r, g, b, fillAlpha];
      },
      getLineColor: (f) =>
        (f.properties as { ward_id: string }).ward_id === sel ? [55, 208, 230, 255] : [8, 20, 24, 200],
      getLineWidth: (f) => ((f.properties as { ward_id: string }).ward_id === sel ? 2.4 : 0.5),
      lineWidthUnits: "pixels",
      lineWidthMinPixels: 0.5,
      onHover: (info) => state.current.onHover((info.object?.properties as { ward_id?: string })?.ward_id ?? null),
      onClick: (info) => {
        const id = (info.object?.properties as { ward_id?: string })?.ward_id ?? null;
        state.current.onSelect(id === state.current.selectedWard ? null : id);
      },
      updateTriggers: {
        getFillColor: [vb, sat],
        getLineColor: [sel],
        getLineWidth: [sel],
      },
    });

    const layers: Layer[] = [layer];
    const rd = state.current.roads;
    if (rd) {
      layers.push(
        new GeoJsonLayer({
          id: "roads",
          data: rd as unknown as GeoJSON.FeatureCollection,
          stroked: true,
          filled: false,
          getLineColor: [244, 239, 228, 130],
          getLineWidth: (f) => {
            const c = (f.properties as { class?: string } | null)?.class;
            return c === "motorway" || c === "trunk" ? 1.4 : 0.9;
          },
          lineWidthUnits: "pixels",
          lineWidthMinPixels: 0.5,
          parameters: { depthTest: false },
        }),
      );
    }
    overlay.setProps({ layers });
  }

  function updateGibs() {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if (map.getLayer("gibs")) map.removeLayer("gibs");
    if (map.getSource("gibs")) map.removeSource("gibs");
    const sat = state.current.satellite;
    if (sat === "off") return;
    const { url, maxzoom } = gibsTiles(sat);
    map.addSource("gibs", { type: "raster", tiles: [url], tileSize: 256, maxzoom, attribution: "NASA GIBS" });
    map.addLayer({ id: "gibs", type: "raster", source: "gibs", paint: { "raster-opacity": GIBS_LAYERS[sat].opacity } }, "bg" === map.getStyle().layers[0]?.id ? undefined : undefined);
    // ensure gibs sits directly above background (below deck overlay, which is non-interleaved)
    map.moveLayer("gibs");
  }

  // React to data / selection / satellite changes.
  useEffect(() => {
    if (mapRef.current?.isStyleLoaded()) updateOverlay();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewById, selectedWard, satellite]);

  useEffect(() => {
    if (mapRef.current?.isStyleLoaded()) updateGibs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [satellite]);

  return <div ref={containerRef} className="h-full w-full" />;
}

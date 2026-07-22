"use client";

import { create } from "zustand";
import type { Lang } from "./i18n";

export type SatelliteLayer = "off" | "no2" | "aod" | "viirs";
export type TimelineH = 0 | 24 | 48 | 72;

interface UIState {
  /** Currently focused ward (shared: map <-> panels). */
  selectedWardId: string | null;
  hoveredWardId: string | null;
  /** Advisory / label language. */
  language: Lang;
  /** Timeline position; 0 = nowcast (t=0 seam), else forecast horizon. */
  timelineH: TimelineH;
  /** 1km grid overlay on/off. */
  gridLayer: boolean;
  /** GIBS satellite overlay selection. */
  satellite: SatelliteLayer;
  /** Replay mode (out-of-fold historical window). */
  replayActive: boolean;
  replayDate: string | null;

  setSelectedWard: (id: string | null) => void;
  setHoveredWard: (id: string | null) => void;
  setLanguage: (l: Lang) => void;
  setTimelineH: (h: TimelineH) => void;
  toggleGrid: () => void;
  setSatellite: (s: SatelliteLayer) => void;
  setReplay: (active: boolean, date?: string | null) => void;
  resetForCity: (language: Lang) => void;
}

export const useUIStore = create<UIState>((set) => ({
  selectedWardId: null,
  hoveredWardId: null,
  language: "en",
  timelineH: 0,
  gridLayer: false,
  satellite: "off",
  replayActive: false,
  replayDate: null,

  setSelectedWard: (id) => set({ selectedWardId: id }),
  setHoveredWard: (id) => set({ hoveredWardId: id }),
  setLanguage: (language) => set({ language }),
  setTimelineH: (timelineH) => set({ timelineH }),
  toggleGrid: () => set((s) => ({ gridLayer: !s.gridLayer })),
  setSatellite: (satellite) => set({ satellite }),
  setReplay: (replayActive, replayDate = null) => set({ replayActive, replayDate }),
  resetForCity: (language) =>
    set({
      selectedWardId: null,
      hoveredWardId: null,
      language,
      timelineH: 0,
      gridLayer: false,
      satellite: "off",
      replayActive: false,
      replayDate: null,
    }),
}));

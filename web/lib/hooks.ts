"use client";

import { useEffect, useRef, useState } from "react";
import type { ZodType } from "zod";
import { fetchJson, type FetchResult } from "./fetchJson";

export type ResourceState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: string };

/**
 * Fetch + validate a JSON resource with per-panel error isolation. Pass a null
 * url to stay idle (e.g. a file a city does not publish). Aborts in flight on
 * url change / unmount.
 */
export function useResource<T>(
  url: string | null | undefined,
  schema: ZodType<T>,
): ResourceState<T> {
  const [state, setState] = useState<ResourceState<T>>({ status: "idle" });
  // Keep the schema ref stable across renders (module consts already are).
  const schemaRef = useRef(schema);
  schemaRef.current = schema;

  useEffect(() => {
    if (!url) {
      setState({ status: "idle" });
      return;
    }
    const ac = new AbortController();
    setState({ status: "loading" });
    fetchJson(url, schemaRef.current, ac.signal).then((res: FetchResult<T>) => {
      if (ac.signal.aborted) return;
      setState(res.ok ? { status: "ready", data: res.data } : { status: "error", error: res.error });
    });
    return () => ac.abort();
  }, [url]);

  return state;
}

/** Respects prefers-reduced-motion; gates cinematic animation (WCAG 2.3.3). */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReduced(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

/**
 * WebGL2 capability probe for map resilience (acceptance 6): false -> render the
 * static SVG choropleth fallback instead of MapLibre + deck.gl. null while
 * probing (before mount).
 */
export function useWebGL2(): boolean | null {
  const [supported, setSupported] = useState<boolean | null>(null);
  useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl2");
      setSupported(!!gl);
    } catch {
      setSupported(false);
    }
  }, []);
  return supported;
}

/** One-shot mounted flag (guards client-only rendering in a static export). */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}

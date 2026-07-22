"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useResource } from "@/lib/hooks";
import { manifest as manifestSchema } from "@/lib/schemas";
import { MANIFEST_URL } from "@/lib/paths";
import { nearestCity } from "@/lib/haversine";

type GeoState = "idle" | "locating" | "denied" | "unsupported";

/**
 * Small client island for the entry page (spec §6, acceptance 14). Everything
 * else on / is static server HTML; only this button + geolocation logic ship
 * JS. Coordinates are matched on-device against manifest centroids and never
 * sent anywhere. Auto-opens the nearest city only if permission was already
 * granted (no unprompted popup).
 */
export function GeolocationGate() {
  const router = useRouter();
  const manifestState = useResource(MANIFEST_URL, manifestSchema);
  const [geo, setGeo] = useState<GeoState>("idle");

  const locate = useCallback(() => {
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
      setGeo("unsupported");
      return;
    }
    if (manifestState.status !== "ready") return;
    const cities = manifestState.data.cities;
    setGeo("locating");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const match = nearestCity({ lat: pos.coords.latitude, lon: pos.coords.longitude }, cities);
        if (match) router.replace(`/city/${match.city.id}/`);
        else setGeo("idle");
      },
      (err) => setGeo(err.code === err.PERMISSION_DENIED ? "denied" : "unsupported"),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 600_000 },
    );
  }, [manifestState, router]);

  useEffect(() => {
    if (manifestState.status !== "ready") return;
    if (typeof navigator === "undefined" || !navigator.permissions?.query) return;
    let cancelled = false;
    navigator.permissions
      .query({ name: "geolocation" as PermissionName })
      .then((res) => {
        if (!cancelled && res.state === "granted") locate();
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [manifestState.status, locate]);

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={locate}
        disabled={geo === "locating" || manifestState.status !== "ready"}
        className="inline-flex items-center gap-2 rounded-[var(--radius-md)] px-4 py-2.5 text-sm font-semibold text-void disabled:opacity-60"
        style={{ backgroundColor: "var(--color-airglow)" }}
      >
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="12" cy="10" r="3" />
          <path d="M12 21c4-4 7-7.5 7-11a7 7 0 10-14 0c0 3.5 3 7 7 11z" />
        </svg>
        {geo === "locating" ? "Locating..." : "Open my nearest city"}
      </button>
      <span className="text-xs text-ink-mute">
        {geo === "denied"
          ? "Location off. Pick a city below."
          : geo === "unsupported"
            ? "Location unavailable. Pick a city below."
            : "Matched on your device. Coordinates never leave your browser."}
      </span>
    </div>
  );
}

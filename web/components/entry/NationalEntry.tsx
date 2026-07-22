"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useResource } from "@/lib/hooks";
import { manifest as manifestSchema } from "@/lib/schemas";
import { MANIFEST_URL } from "@/lib/paths";
import { nearestCity } from "@/lib/haversine";
import { cn } from "@/lib/cn";
import { Wordmark } from "@/components/chrome/Brandmark";
import { Badge } from "@/components/ui/Badge";

type GeoState = "idle" | "locating" | "denied" | "unsupported";

const CITIES = [
  {
    id: "delhi",
    name: "Delhi",
    tier: "deep" as const,
    blurb: "Full command center, 24 to 72h forecast, source attribution, enforcement queue, and the Intervention Ledger.",
  },
  {
    id: "mumbai",
    name: "Mumbai",
    tier: "standard" as const,
    blurb: "Nowcast, ward forecast, and citizen advisories in Marathi and Hindi.",
  },
  {
    id: "bengaluru",
    name: "Bengaluru",
    tier: "config-only" as const,
    blurb: "Live from a single YAML config. Adding a new city is one file.",
  },
];

const TIER_LABEL: Record<string, string> = {
  deep: "Deep coverage",
  standard: "Standard",
  "config-only": "Config-only",
};

export function NationalEntry() {
  const router = useRouter();
  const manifestState = useResource(MANIFEST_URL, manifestSchema);
  const [geo, setGeo] = useState<GeoState>("idle");
  const [nearest, setNearest] = useState<string | null>(null);

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
        // Coordinates are matched ON DEVICE and never sent anywhere.
        const match = nearestCity({ lat: pos.coords.latitude, lon: pos.coords.longitude }, cities);
        if (match) {
          setNearest(match.city.id);
          router.replace(`/city/${match.city.id}/`);
        } else {
          setGeo("idle");
        }
      },
      (err) => setGeo(err.code === err.PERMISSION_DENIED ? "denied" : "unsupported"),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 600_000 },
    );
  }, [manifestState, router]);

  // Auto-open only if permission was already granted (no unprompted popup).
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
    <main id="main" className="relative isolate flex min-h-dvh flex-col overflow-hidden">
      <AtmosphericField />

      <div className="mx-auto flex w-full max-w-[1180px] flex-1 flex-col px-4 py-5 sm:px-6">
        <div className="flex items-center justify-between">
          <Wordmark />
          <nav aria-label="Primary" className="flex items-center gap-4 text-sm text-ink-mute">
            <Link href="/ledger/" className="hover:text-ink">Ledger</Link>
            <Link href="/receipts/" className="hover:text-ink">Receipts</Link>
            <Link href="/pitch/" className="hover:text-ink">Pitch</Link>
          </nav>
        </div>

        <div className="flex flex-1 flex-col justify-center py-12">
          <p className="eyebrow">National air quality intelligence · open data</p>
          <h1 className="mt-3 max-w-3xl text-5xl leading-[1.02] sm:text-6xl">
            See your city&rsquo;s air, <span className="text-airglow">ward by ward.</span>
          </h1>
          <p className="mt-4 max-w-xl text-lg text-ink-soft">
            Gap-filled nowcast, ward-level forecast, source attribution, and an enforcement queue for
            Indian cities. Every number from a real public source. Every model claim with a validation
            receipt.
          </p>

          {/* Geolocation gate */}
          <div className="mt-7 flex flex-wrap items-center gap-3">
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

          {/* Ledger lead */}
          <Link
            href="/ledger/"
            className="group mt-8 flex max-w-2xl items-center justify-between gap-4 rounded-[var(--radius-lg)] border p-4 transition-colors"
            style={{ borderColor: "var(--line-airglow)", background: "var(--color-airglow-ghost)" }}
          >
            <span>
              <span className="flex items-center gap-2">
                <Badge tone="accent">World-first</Badge>
                <span className="eyebrow">Intervention Ledger</span>
              </span>
              <span className="mt-1.5 block text-lg text-ink">
                Did Delhi&rsquo;s emergency measures actually work?
              </span>
              <span className="mt-0.5 block text-sm text-ink-mute">
                Weather-adjusted, ward by ward, with modeled lives saved and what acting earlier would
                have changed.
              </span>
            </span>
            <span aria-hidden className="text-2xl text-airglow transition-transform group-hover:translate-x-1">
              &rarr;
            </span>
          </Link>

          {/* City picker (always visible) */}
          <div className="mt-10">
            <p className="eyebrow mb-3">Or open a command center</p>
            <ul className="grid gap-3 sm:grid-cols-3">
              {CITIES.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/city/${c.id}/`}
                    className={cn(
                      "flex h-full flex-col rounded-[var(--radius-md)] border p-4 transition-colors hover:border-[var(--line-airglow)]",
                      nearest === c.id && "ring-1",
                    )}
                    style={{
                      borderColor: nearest === c.id ? "var(--line-airglow)" : "var(--line)",
                      background: "color-mix(in oklab, var(--color-surface) 55%, transparent)",
                    }}
                    aria-current={nearest === c.id ? "true" : undefined}
                  >
                    <span className="flex items-center justify-between">
                      <span className="text-lg font-semibold text-ink">{c.name}</span>
                      <Badge tone={c.tier === "deep" ? "accent" : "outline"}>{TIER_LABEL[c.tier]}</Badge>
                    </span>
                    <span className="mt-1.5 text-xs text-ink-mute">{c.blurb}</span>
                    {nearest === c.id && <span className="mt-2 text-[0.7rem] text-airglow">Nearest to you</span>}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="text-xs text-ink-dim">
          Prototype for the ET AI Hackathon 2026. Sources and gaps documented on{" "}
          <Link href="/about-data/" className="text-airglow">
            the data page
          </Link>
          .
        </p>
      </div>
    </main>
  );
}

/** Decorative atmospheric backdrop: concentric orbital rings + drifting haze. */
function AtmosphericField() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <svg className="absolute left-1/2 top-[38%] h-[130vmin] w-[130vmin] -translate-x-1/2 -translate-y-1/2 opacity-[0.5]" viewBox="0 0 100 100" fill="none">
        {[46, 38, 30, 22].map((r, i) => (
          <circle key={r} cx="50" cy="50" r={r} stroke="var(--color-airglow)" strokeOpacity={0.06 + i * 0.015} strokeWidth={0.15} />
        ))}
      </svg>
      <div className="bg-grid absolute inset-0 opacity-40" />
    </div>
  );
}

import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Wordmark } from "@/components/chrome/Brandmark";
import { GeolocationGate } from "@/components/entry/GeolocationGate";

const CITIES = [
  { id: "delhi", name: "Delhi", tier: "deep" as const, blurb: "Full command center, 24 to 72h forecast, source attribution, enforcement queue, and the Intervention Ledger." },
  { id: "mumbai", name: "Mumbai", tier: "standard" as const, blurb: "Nowcast, ward forecast, and citizen advisories in Marathi and Hindi." },
  { id: "bengaluru", name: "Bengaluru", tier: "config-only" as const, blurb: "Live from a single YAML config. Adding a new city is one file." },
];

const TIER_LABEL: Record<string, string> = {
  deep: "Deep coverage",
  standard: "Standard",
  "config-only": "Config-only",
};

export default function Home() {
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

          <div className="mt-7">
            <GeolocationGate />
          </div>

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
              <span className="mt-1.5 block text-lg text-ink">Did Delhi&rsquo;s emergency measures actually work?</span>
              <span className="mt-0.5 block text-sm text-ink-mute">
                Weather-adjusted, ward by ward, with modeled lives saved and what acting earlier would
                have changed.
              </span>
            </span>
            <span aria-hidden className="text-2xl text-airglow transition-transform group-hover:translate-x-1">&rarr;</span>
          </Link>

          <div className="mt-10">
            <p className="eyebrow mb-3">Or open a command center</p>
            <ul className="grid gap-3 sm:grid-cols-3">
              {CITIES.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/city/${c.id}/`}
                    className="flex h-full flex-col rounded-[var(--radius-md)] border p-4 transition-colors hover:border-[var(--line-airglow)]"
                    style={{ borderColor: "var(--line)", background: "color-mix(in oklab, var(--color-surface) 55%, transparent)" }}
                  >
                    <span className="flex items-center justify-between">
                      <span className="text-lg font-semibold text-ink">{c.name}</span>
                      <Badge tone={c.tier === "deep" ? "accent" : "outline"}>{TIER_LABEL[c.tier]}</Badge>
                    </span>
                    <span className="mt-1.5 text-xs text-ink-mute">{c.blurb}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="text-xs text-ink-dim">
          Prototype for the ET AI Hackathon 2026. Sources and gaps documented on{" "}
          <Link href="/about-data/" className="text-airglow">the data page</Link>.
        </p>
      </div>
    </main>
  );
}

/** Decorative atmospheric backdrop: concentric orbital rings + faint grid. */
function AtmosphericField() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <svg className="absolute left-1/2 top-[38%] h-[130vmin] w-[130vmin] -translate-x-1/2 -translate-y-1/2 opacity-50" viewBox="0 0 100 100" fill="none">
        {[46, 38, 30, 22].map((r, i) => (
          <circle key={r} cx="50" cy="50" r={r} stroke="var(--color-airglow)" strokeOpacity={0.06 + i * 0.015} strokeWidth={0.15} />
        ))}
      </svg>
      <div className="bg-grid absolute inset-0 opacity-40" />
    </div>
  );
}

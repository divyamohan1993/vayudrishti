"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Wordmark } from "@/components/chrome/Brandmark";

interface Slide {
  eyebrow: string;
  title: string;
  body: ReactNode;
}

const SLIDES: Slide[] = [
  {
    eyebrow: "ET AI Hackathon 2026",
    title: "Air quality intelligence that proves whether the fixes work.",
    body: (
      <p className="max-w-2xl text-lg text-ink-soft">
        VayuDrishti closes the loop from a pollution number to an accountable action. For the first
        time, weather-adjusted and ward by ward, you can prove whether Delhi&rsquo;s emergency measures
        actually worked.
      </p>
    ),
  },
  {
    eyebrow: "The gap",
    title: "900+ stations. No intelligence layer.",
    body: (
      <div className="grid max-w-3xl gap-6 sm:grid-cols-3">
        {[
          ["900+", "CAAQMS stations measuring the air"],
          ["31%", "of monitored cities have a response protocol (CAG)"],
          ["0", "systems that prove whether emergency measures worked"],
        ].map(([n, l]) => (
          <div key={l}>
            <p className="tabular text-4xl font-semibold text-airglow">{n}</p>
            <p className="mt-1 text-sm text-ink-mute">{l}</p>
          </div>
        ))}
      </div>
    ),
  },
  {
    eyebrow: "The loop, closed",
    title: "From a number to an accountable action.",
    body: (
      <div className="max-w-3xl">
        <ol className="flex flex-wrap items-center gap-2 text-sm">
          {["Nowcast", "Forecast", "Attribution", "Enforcement", "Advisories", "Ledger"].map((s, i, a) => (
            <li key={s} className="flex items-center gap-2">
              <span className="rounded-full border px-3 py-1 text-ink" style={{ borderColor: "var(--line-airglow)" }}>{s}</span>
              {i < a.length - 1 && <span aria-hidden className="text-airglow">&rarr;</span>}
            </li>
          ))}
        </ol>
        <p className="mt-6 text-lg text-ink-soft">
          Every number from a real, free, public source. Every model claim shipped with a validation
          receipt.
        </p>
      </div>
    ),
  },
  {
    eyebrow: "World-first capability",
    title: "The Intervention Ledger.",
    body: (
      <div className="max-w-3xl">
        <p className="text-lg text-ink-soft">
          Weather-adjusted, ward by ward: did each GRAP stage cut pollution? What would acting earlier
          have saved in lives?
        </p>
        <div className="mt-6 grid gap-6 sm:grid-cols-3">
          <div>
            <p className="tabular text-4xl font-semibold" style={{ color: "var(--color-div-neg-1)" }}>243</p>
            <p className="mt-1 text-sm text-ink-mute">modeled lives saved this winter (with CI)</p>
          </div>
          <div>
            <p className="tabular text-4xl font-semibold" style={{ color: "var(--color-div-neg-1)" }}>31.7</p>
            <p className="mt-1 text-sm text-ink-mute">µg/m³ cut by GRAP Stage IV (placebo-passed)</p>
          </div>
          <div>
            <p className="tabular text-4xl font-semibold text-ember">1</p>
            <p className="mt-1 text-sm text-ink-mute">stage with no detectable effect. We publish that too.</p>
          </div>
        </div>
      </div>
    ),
  },
  {
    eyebrow: "Under the hood",
    title: "Research-grade methods, composed.",
    body: (
      <ul className="grid max-w-3xl gap-3 text-sm text-ink-soft sm:grid-cols-2">
        {[
          "Ensemble gap-fill: IDW, kriging, satellite AOD-to-PM, and LightGBM, stacked on out-of-fold folds",
          "Deweathering (Grange & Carslaw 2019) removes the weather confound",
          "Event-study with placebo tests and block-bootstrap confidence intervals",
          "GEMM exposure-response (Burnett 2018) with WorldPop population",
          "Nemotron reasoning agents draft verified, evidence-cited action briefs",
          "Five real satellites, zero-auth GIBS visuals plus keyed numeric features",
        ].map((t) => (
          <li key={t} className="flex gap-2">
            <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: "var(--color-airglow)" }} />
            {t}
          </li>
        ))}
      </ul>
    ),
  },
  {
    eyebrow: "Why us",
    title: "Honesty is the moat.",
    body: (
      <div className="max-w-2xl">
        <p className="text-lg text-ink-soft">
          24-hour forecast skill <span className="tabular font-semibold" style={{ color: "var(--color-div-neg-1)" }}>+16.8%</span>.
          72-hour skill <span className="tabular font-semibold text-ember">-3.3%</span>, shown in red. Null
          findings published. Validated against an embassy network we never trained on.
        </p>
        <p className="mt-5 text-ink-mute">
          In a crowded AQI field, we lead with receipts in the first thirty seconds, not claims.
        </p>
      </div>
    ),
  },
  {
    eyebrow: "Who acts, and why",
    title: "Evidence in the room where decisions are made.",
    body: (
      <div className="grid max-w-3xl gap-6 sm:grid-cols-3">
        {[
          ["Officer", "A ranked enforcement queue with evidence cards: which ward, which source, which action."],
          ["Citizen", "A ward advisory in their own language, from the same validated forecast."],
          ["Public", "Accountability for every rupee spent on emergency measures."],
        ].map(([h, l]) => (
          <div key={h}>
            <p className="text-lg font-semibold text-ink">{h}</p>
            <p className="mt-1.5 text-sm text-ink-mute">{l}</p>
          </div>
        ))}
      </div>
    ),
  },
  {
    eyebrow: "Scale",
    title: "Add a city in one file.",
    body: (
      <div className="max-w-2xl">
        <p className="text-lg text-ink-soft">
          Bengaluru is live from a single YAML config. Static, edge-first, free-tier, with Cloudflare in
          front. From one city to every Indian city without ripping anything out.
        </p>
        <pre className="tabular mt-6 overflow-x-auto rounded-[var(--radius-md)] border p-4 text-xs text-airglow" style={{ borderColor: "var(--line)", background: "var(--color-void)" }}>
{`# config/cities/bengaluru.yaml
bbox: [77.46, 12.83, 77.78, 13.14]
wards: { source: bbmp, ward_id_field: WARD_NO }
languages: [kn, en]`}
        </pre>
      </div>
    ),
  },
  {
    eyebrow: "What is next",
    title: "From audit to copilot.",
    body: (
      <ul className="grid max-w-3xl gap-3 text-ink-soft sm:grid-cols-2">
        {[
          "More cities, same pipeline",
          "GEMS and INSAT geostationary satellites: Indian satellites for Indian air",
          "Live keyed data (data.gov.in CPCB snapshot)",
          "Commissioner's Copilot: ask the ledger a question",
        ].map((t) => (
          <li key={t} className="flex gap-2 text-sm">
            <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: "var(--color-airglow)" }} />
            {t}
          </li>
        ))}
      </ul>
    ),
  },
  {
    eyebrow: "See it live",
    title: "Every number real. Every claim receipted.",
    body: (
      <div className="flex max-w-2xl flex-col gap-6">
        <p className="text-lg text-ink-soft">Open the command center. Read the receipts. Judge for yourself.</p>
        <div className="flex flex-wrap gap-3">
          <Link href="/ledger/" className="rounded-[var(--radius-md)] px-4 py-2.5 text-sm font-semibold text-void" style={{ background: "var(--color-airglow)" }}>
            Intervention Ledger
          </Link>
          <Link href="/receipts/" className="rounded-[var(--radius-md)] border px-4 py-2.5 text-sm text-ink" style={{ borderColor: "var(--line-airglow)" }}>
            Receipts
          </Link>
          <Link href="/city/delhi/" className="rounded-[var(--radius-md)] border px-4 py-2.5 text-sm text-ink" style={{ borderColor: "var(--line)" }}>
            Command Center
          </Link>
        </div>
      </div>
    ),
  },
];

export function PitchDeck() {
  const [i, setI] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const n = SLIDES.length;

  const go = useCallback((next: number) => setI(Math.max(0, Math.min(n - 1, next))), [n]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (["ArrowRight", "PageDown", " "].includes(e.key)) {
        e.preventDefault();
        setI((c) => Math.min(n - 1, c + 1));
      } else if (["ArrowLeft", "PageUp"].includes(e.key)) {
        e.preventDefault();
        setI((c) => Math.max(0, c - 1));
      } else if (e.key === "Home") {
        setI(0);
      } else if (e.key === "End") {
        setI(n - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [n]);

  const slide = SLIDES[i];

  return (
    <main id="main" ref={rootRef} className="relative flex min-h-dvh flex-col">
      <div className="bg-grid pointer-events-none absolute inset-0 -z-10 opacity-40" />
      <header className="flex items-center justify-between px-5 py-4 sm:px-8">
        <Wordmark />
        <Link href="/" className="text-sm text-ink-mute hover:text-ink">
          Exit deck
        </Link>
      </header>

      <section
        key={i}
        className="animate-rise flex flex-1 flex-col justify-center px-5 py-8 sm:px-12"
        aria-roledescription="slide"
        aria-label={`Slide ${i + 1} of ${n}: ${slide.title}`}
      >
        <p className="eyebrow">
          {String(i + 1).padStart(2, "0")} · {slide.eyebrow}
        </p>
        <h1 className="mt-3 max-w-4xl text-4xl leading-tight sm:text-6xl">{slide.title}</h1>
        <div className="mt-8">{slide.body}</div>
      </section>

      <p className="sr-only" aria-live="polite">
        Slide {i + 1} of {n}: {slide.title}
      </p>

      <footer className="flex items-center justify-between gap-4 border-t px-5 py-4 sm:px-8" style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center gap-2" role="tablist" aria-label="Slides">
          {SLIDES.map((s, k) => (
            <button
              key={k}
              role="tab"
              aria-selected={k === i}
              aria-label={`Slide ${k + 1}: ${s.title}`}
              onClick={() => go(k)}
              className={cn("h-2 rounded-full transition-all", k === i ? "w-6" : "w-2 hover:opacity-80")}
              style={{ background: k === i ? "var(--color-airglow)" : "var(--color-surface-3)" }}
            />
          ))}
        </div>
        <div className="flex items-center gap-3">
          <span className="tabular text-sm text-ink-mute">
            {i + 1} / {n}
          </span>
          <button
            type="button"
            onClick={() => go(i - 1)}
            disabled={i === 0}
            className="rounded-md border px-3 py-1.5 text-sm text-ink disabled:opacity-40"
            style={{ borderColor: "var(--line)" }}
          >
            Prev
          </button>
          <button
            type="button"
            onClick={() => go(i + 1)}
            disabled={i === n - 1}
            className="rounded-md px-3 py-1.5 text-sm font-medium text-void disabled:opacity-40"
            style={{ background: "var(--color-airglow)" }}
          >
            Next
          </button>
        </div>
      </footer>
    </main>
  );
}

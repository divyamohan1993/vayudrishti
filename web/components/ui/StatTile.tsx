import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "neutral" | "accent" | "good" | "bad" | "warn";

const TONE_COLOR: Record<Tone, string> = {
  neutral: "var(--color-ink)",
  accent: "var(--color-airglow)",
  good: "var(--color-div-neg-1)",
  bad: "var(--color-div-pos-1)",
  warn: "var(--color-ember)",
};

/**
 * A single instrument readout: eyebrow label, a large tabular value, optional
 * unit and sub-line (e.g. a CI range). The number is the signal; keep it mono.
 */
export function StatTile({
  label,
  value,
  unit,
  sub,
  tone = "neutral",
  size = "md",
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  sub?: ReactNode;
  tone?: Tone;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const valueSize =
    size === "lg" ? "text-4xl sm:text-5xl" : size === "sm" ? "text-xl" : "text-2xl sm:text-3xl";
  return (
    <div className={cn("flex flex-col", className)}>
      <p className="eyebrow">{label}</p>
      <p className={cn("tabular mt-1.5 font-semibold leading-none", valueSize)} style={{ color: TONE_COLOR[tone] }}>
        {value}
        {unit && <span className="ml-1 text-[0.5em] font-medium text-ink-mute">{unit}</span>}
      </p>
      {sub && <p className="mt-1.5 text-xs leading-snug text-ink-mute">{sub}</p>}
    </div>
  );
}

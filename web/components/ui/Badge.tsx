import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "neutral" | "accent" | "good" | "bad" | "warn" | "outline";

function toneStyle(tone: Tone): CSSProperties {
  switch (tone) {
    case "accent":
      return {
        color: "var(--color-airglow)",
        borderColor: "var(--line-airglow)",
        backgroundColor: "var(--color-airglow-ghost)",
      };
    case "good":
      return {
        color: "var(--color-div-neg-1)",
        borderColor: "color-mix(in oklab, var(--color-div-neg-1) 42%, transparent)",
      };
    case "bad":
      return {
        color: "var(--color-div-pos-1)",
        borderColor: "color-mix(in oklab, var(--color-div-pos-1) 42%, transparent)",
      };
    case "warn":
      return {
        color: "var(--color-ember)",
        borderColor: "color-mix(in oklab, var(--color-ember) 42%, transparent)",
      };
    case "outline":
      return { color: "var(--color-ink-mute)", borderColor: "var(--line)" };
    default:
      return {
        color: "var(--color-ink-soft)",
        borderColor: "var(--line)",
        backgroundColor: "var(--color-surface-2)",
      };
  }
}

export function Badge({
  children,
  tone = "neutral",
  className,
  icon,
  title,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
  icon?: ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.7rem] font-medium",
        className,
      )}
      style={toneStyle(tone)}
    >
      {icon}
      {children}
    </span>
  );
}

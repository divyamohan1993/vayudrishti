import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "error" | "empty" | "info";

/**
 * Centered note for a panel body when data is unavailable, empty, or degraded.
 * Per-panel isolation (spec §6): one bad file shows this, never a blank crash.
 */
export function StatusNote({
  tone = "info",
  title,
  message,
  className,
  action,
}: {
  tone?: Tone;
  title: ReactNode;
  message?: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  const accent =
    tone === "error" ? "var(--color-div-pos-1)" : tone === "empty" ? "var(--color-ink-dim)" : "var(--color-airglow)";
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "flex h-full min-h-24 flex-col items-center justify-center gap-1.5 rounded-md border border-dashed p-6 text-center",
        className,
      )}
      style={{ borderColor: "var(--line)" }}
    >
      <span
        aria-hidden
        className="mb-1 inline-block h-2 w-2 rounded-full"
        style={{ backgroundColor: accent }}
      />
      <p className="text-sm font-medium text-ink-soft">{title}</p>
      {message && <p className="max-w-xs text-xs text-ink-mute">{message}</p>}
      {action}
    </div>
  );
}

import { cn } from "@/lib/cn";

/**
 * VayuDrishti mark: an orbital aperture — atmospheric rings around a sensing
 * focal point (drishti = vision), with instrument crosshair ticks. Geometric,
 * recognisable small, inherits currentColor for the rings with an airglow pupil.
 */
export function Brandmark({
  className,
  title = "VayuDrishti",
}: {
  className?: string;
  title?: string;
}) {
  return (
    <svg
      viewBox="0 0 32 32"
      role="img"
      aria-label={title}
      className={cn("shrink-0", className)}
      fill="none"
    >
      <title>{title}</title>
      {/* Atmospheric limb rings */}
      <circle cx="16" cy="16" r="13" stroke="currentColor" strokeOpacity="0.3" strokeWidth="1.2" />
      <circle cx="16" cy="16" r="9" stroke="currentColor" strokeOpacity="0.55" strokeWidth="1.2" />
      {/* Instrument crosshair ticks */}
      <g stroke="currentColor" strokeOpacity="0.7" strokeWidth="1.4" strokeLinecap="round">
        <path d="M16 1.5V5" />
        <path d="M16 27V30.5" />
        <path d="M1.5 16H5" />
        <path d="M27 16H30.5" />
      </g>
      {/* Sensing focal point */}
      <circle cx="16" cy="16" r="3.4" fill="var(--color-airglow)" />
      <circle cx="16" cy="16" r="6" stroke="var(--color-airglow)" strokeOpacity="0.5" strokeWidth="1" />
    </svg>
  );
}

/** Full lockup: mark + wordmark (Vayu in ink, Drishti in airglow). */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <Brandmark className="h-7 w-7 text-ink" />
      <span
        className="text-[1.05rem] font-semibold tracking-tight"
        style={{ fontFamily: "var(--font-display)" }}
      >
        <span className="text-ink">Vayu</span>
        <span className="text-airglow">Drishti</span>
      </span>
    </span>
  );
}

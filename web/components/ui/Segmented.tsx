"use client";

import { useRef } from "react";
import { cn } from "@/lib/cn";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  disabled?: boolean;
}

/**
 * Accessible segmented control (radiogroup + roving tabindex + arrow keys).
 * Used for language switch, layer selection, timeline snap, etc.
 */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  size = "md",
  className,
}: {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (v: T) => void;
  ariaLabel: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function focusIndex(i: number) {
    const n = options.length;
    const idx = ((i % n) + n) % n;
    refs.current[idx]?.focus();
    onChange(options[idx].value);
  }

  function onKeyDown(e: React.KeyboardEvent, i: number) {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      focusIndex(i + 1);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      focusIndex(i - 1);
    }
  }

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-[var(--radius-sm)] border p-0.5",
        className,
      )}
      style={{ borderColor: "var(--line)", backgroundColor: "var(--color-deep)" }}
    >
      {options.map((o, i) => {
        const selected = o.value === value;
        return (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            disabled={o.disabled}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              "rounded-[5px] font-medium transition-colors disabled:opacity-40",
              size === "sm" ? "px-2 py-0.5 text-[0.7rem]" : "px-2.5 py-1 text-xs",
              selected ? "text-ink" : "text-ink-mute hover:text-ink-soft",
            )}
            style={selected ? { backgroundColor: "var(--color-surface-3)" } : undefined}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

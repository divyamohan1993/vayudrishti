import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * The instrument-glass surface every command-center module sits on. A single
 * disciplined container: hairline border, atmospheric blur, optional header row
 * with an eyebrow/title and actions. Landmark-friendly (renders as <section> by
 * default; pass aria-label for screen-reader naming).
 */
export function Panel({
  title,
  eyebrow,
  actions,
  children,
  className,
  bodyClassName,
  as: Tag = "section",
  padded = true,
  "aria-label": ariaLabel,
}: {
  title?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  as?: "section" | "div" | "article" | "aside";
  padded?: boolean;
  "aria-label"?: string;
}) {
  const hasHeader = title || eyebrow || actions;
  return (
    <Tag className={cn("panel flex min-h-0 flex-col", className)} aria-label={ariaLabel}>
      {hasHeader && (
        <header className="flex items-start justify-between gap-3 border-b border-[var(--line)] px-4 py-3">
          <div className="min-w-0">
            {eyebrow && <p className="eyebrow mb-0.5">{eyebrow}</p>}
            {title && (
              <h2 className="truncate text-[0.95rem] font-semibold text-ink">{title}</h2>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn(padded && "p-4", "min-h-0 flex-1", bodyClassName)}>{children}</div>
    </Tag>
  );
}

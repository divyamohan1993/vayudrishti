"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { Wordmark } from "./Brandmark";

interface NavItem {
  href: string;
  label: string;
  match?: string;
}

const NAV: NavItem[] = [
  { href: "/ledger", label: "Intervention Ledger" },
  { href: "/city/delhi", label: "Command Center", match: "/city" },
  { href: "/receipts", label: "Receipts" },
  { href: "/methods", label: "Methods" },
  { href: "/about-data", label: "Data" },
];

export function AppHeader() {
  const pathname = usePathname() ?? "";
  const [open, setOpen] = useState(false);

  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const isActive = (item: NavItem) =>
    item.match ? pathname.startsWith(item.match) : pathname === item.href || pathname === `${item.href}/`;

  return (
    <header
      className="sticky top-0 z-50 border-b"
      style={{
        borderColor: "var(--line)",
        background: "color-mix(in oklab, var(--color-abyss) 86%, transparent)",
        backdropFilter: "blur(12px) saturate(1.1)",
      }}
    >
      <div className="mx-auto flex h-14 max-w-[1680px] items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" aria-label="VayuDrishti home" className="rounded-md">
          <Wordmark />
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-0.5 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(item) ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm transition-colors",
                isActive(item) ? "text-ink" : "text-ink-mute hover:text-ink-soft",
              )}
              style={isActive(item) ? { backgroundColor: "var(--color-surface)" } : undefined}
            >
              {item.label}
            </Link>
          ))}
          <Link
            href="/pitch"
            className="ml-2 rounded-md border px-3 py-1.5 text-sm text-airglow transition-colors hover:bg-[var(--color-airglow-ghost)]"
            style={{ borderColor: "var(--line-airglow)" }}
          >
            Pitch
          </Link>
        </nav>

        <button
          type="button"
          className="inline-flex h-9 w-9 items-center justify-center rounded-md border text-ink md:hidden"
          style={{ borderColor: "var(--line)" }}
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
            {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
      </div>

      {open && (
        <nav id="mobile-nav" aria-label="Primary" className="border-t md:hidden" style={{ borderColor: "var(--line)" }}>
          <ul className="mx-auto flex max-w-[1680px] flex-col px-4 py-2 sm:px-6">
            {[...NAV, { href: "/pitch", label: "Pitch" }].map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={isActive(item) ? "page" : undefined}
                  className={cn(
                    "block rounded-md px-3 py-2.5 text-sm",
                    isActive(item) ? "text-ink" : "text-ink-soft",
                  )}
                  style={isActive(item) ? { backgroundColor: "var(--color-surface)" } : undefined}
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </header>
  );
}

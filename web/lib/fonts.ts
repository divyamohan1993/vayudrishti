import localFont from "next/font/local";

/**
 * Self-hosted variable fonts (latin wght subset, OFL — see web/fonts/ATTRIBUTION.md).
 * Loaded via next/font/local so they are same-origin (CSP font-src 'self'),
 * preloaded, and swap-safe with a sized fallback (no layout shift, good LCP).
 * Deliberately not Inter / Space Grotesk / JetBrains Mono.
 */

export const archivo = localFont({
  src: "../fonts/archivo-latin-wght-normal.woff2",
  variable: "--font-archivo",
  display: "swap",
  weight: "100 900",
  preload: true,
  fallback: ["system-ui", "sans-serif"],
});

export const hanken = localFont({
  src: "../fonts/hanken-grotesk-latin-wght-normal.woff2",
  variable: "--font-hanken",
  display: "swap",
  weight: "100 900",
  preload: true,
  fallback: ["system-ui", "sans-serif"],
});

export const splineMono = localFont({
  src: "../fonts/spline-sans-mono-latin-wght-normal.woff2",
  variable: "--font-spline-mono",
  display: "swap",
  weight: "300 700",
  preload: true,
  fallback: ["ui-monospace", "monospace"],
});

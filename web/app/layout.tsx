import type { Metadata, Viewport } from "next";
import { archivo, hanken, splineMono } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "VayuDrishti — Urban Air Quality Intelligence",
    template: "%s · VayuDrishti",
  },
  description:
    "Weather-adjusted, ward-by-ward air quality intelligence for Indian cities: nowcast, 24-72h forecast, source attribution, an enforcement queue, and an Intervention Ledger that audits whether emergency measures actually worked. Every number from a real public source, every model claim shipped with a validation receipt.",
  applicationName: "VayuDrishti",
  keywords: [
    "air quality",
    "CPCB",
    "GRAP",
    "Delhi",
    "PM2.5",
    "forecast",
    "intervention ledger",
  ],
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#081418",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${hanken.variable} ${splineMono.variable}`}
    >
      <body>
        <a href="#main" className="skip-link">
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}

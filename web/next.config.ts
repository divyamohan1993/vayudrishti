import type { NextConfig } from "next";

/**
 * VayuDrishti web — static export.
 *
 * Architecture (spec §6, A4): pure static CDN site, all inference precomputed,
 * client-side fetch of /data/*.json. No server runtime, no privileged ops.
 *
 * SECURITY HEADERS ARE NOT EMITTED HERE. On a static export Next's headers()
 * is inert, so vayu-ops owns every security header in vercel.json (Option B,
 * see spec §7 + exception A13 for the static-export CSP tradeoff). This file
 * is build config only.
 */
const nextConfig: NextConfig = {
  output: "export",
  // Each route resolves to <route>/index.html — portable across any static host
  // and the offline finale, and avoids extension-based routing surprises.
  trailingSlash: true,
  // Static export cannot use the Image Optimization server.
  images: { unoptimized: true },
  reactStrictMode: true,
  // Fail the build on type or lint errors rather than shipping them.
  typescript: { ignoreBuildErrors: false },
  eslint: { ignoreDuringBuilds: false },
};

export default nextConfig;

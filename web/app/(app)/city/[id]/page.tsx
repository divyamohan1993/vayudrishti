import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CityCommandCenter } from "@/components/city/CityCommandCenter";

const FALLBACK = [
  { id: "delhi", name: "Delhi" },
  { id: "mumbai", name: "Mumbai" },
  { id: "bengaluru", name: "Bengaluru" },
];

/**
 * Enumerated from the published manifest at build time, so adding a city is a
 * YAML + pipeline run + redeploy with no code edit (acceptance 5). Falls back to
 * the known three if the manifest is not readable at build.
 */
function cityList(): { id: string; name: string }[] {
  try {
    const raw = readFileSync(join(process.cwd(), "public/data/manifest.json"), "utf8");
    const m = JSON.parse(raw) as { cities?: { id: string; name: string }[] };
    if (Array.isArray(m.cities) && m.cities.length > 0) {
      return m.cities.map((c) => ({ id: c.id, name: c.name }));
    }
  } catch {
    // manifest not available at build; use the known set
  }
  return FALLBACK;
}

export function generateStaticParams() {
  return cityList().map((c) => ({ id: c.id }));
}

export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const name = cityList().find((c) => c.id === id)?.name ?? id;
  return {
    title: `${name} Command Center`,
    description: `Live ward-level air quality command center for ${name}: gap-filled nowcast, 24-72h forecast, source attribution, enforcement queue, and citizen advisories.`,
  };
}

export default async function CityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!cityList().some((c) => c.id === id)) notFound();
  return <CityCommandCenter cityId={id} />;
}

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CityCommandCenter } from "@/components/city/CityCommandCenter";

const CITIES: Record<string, string> = {
  delhi: "Delhi",
  mumbai: "Mumbai",
  bengaluru: "Bengaluru",
};

export function generateStaticParams() {
  return Object.keys(CITIES).map((id) => ({ id }));
}

export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const name = CITIES[id] ?? id;
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
  if (!CITIES[id]) notFound();
  return <CityCommandCenter cityId={id} />;
}

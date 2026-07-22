import type { Metadata } from "next";
import { AboutDataPage } from "@/components/about/AboutDataPage";

export const metadata: Metadata = {
  title: "Data and sources",
  description:
    "Every number in VayuDrishti traces to a real, free, public source. Sources, coverage and gaps, ward vintage notes, the CPCB AQI methodology table, satellite status, and the agent-layer transparency trace.",
};

export default function Page() {
  return <AboutDataPage />;
}

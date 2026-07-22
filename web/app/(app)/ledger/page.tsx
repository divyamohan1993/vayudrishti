import type { Metadata } from "next";
import { LedgerPage } from "@/components/ledger/LedgerPage";

export const metadata: Metadata = {
  title: "Intervention Ledger — did Delhi's emergency measures work?",
  description:
    "The first operational, weather-adjusted, ward-by-ward audit of whether Delhi's GRAP emergency measures actually cut PM2.5, with modeled avoided-mortality estimates and counterfactual timing. Every number carries a confidence interval; every date cites a CAQM order.",
};

export default function Page() {
  return <LedgerPage cityId="delhi" />;
}

import type { Metadata } from "next";
import { ReceiptsPage } from "@/components/receipts/ReceiptsPage";

export const metadata: Metadata = {
  title: "Receipts: every claim, its validation number",
  description:
    "The evidence page: stratified LOSO cross-validation curves, honest forecast skill (positive and negative), source-attribution directional checks, the Intervention Ledger novelty statement and prior art, the CPCB methodology table, and full data lineage.",
};

export default function Page() {
  return <ReceiptsPage />;
}

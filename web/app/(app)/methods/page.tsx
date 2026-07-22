import type { Metadata } from "next";
import { MethodsPage } from "@/components/methods/MethodsPage";

export const metadata: Metadata = {
  title: "Methods",
  description:
    "The scientific centerpiece: known gaps in existing air-quality systems, each closed by a pair of peer-reviewed techniques that cover each other's failure modes. Ensemble gap-fill, deweathering, causal effect estimation, trajectory attribution, and GEMM health translation, with downloadable data products.",
};

export default function Page() {
  return <MethodsPage />;
}

import type { Metadata } from "next";
import { PitchDeck } from "@/components/pitch/PitchDeck";

export const metadata: Metadata = {
  title: "Pitch",
  description: "VayuDrishti in ten slides: the world-first Intervention Ledger, the intelligence stack, and honesty as the differentiator.",
};

export default function Page() {
  return <PitchDeck />;
}

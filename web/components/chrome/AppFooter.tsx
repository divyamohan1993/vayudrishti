import Link from "next/link";
import { Brandmark } from "./Brandmark";

export function AppFooter() {
  return (
    <footer className="mt-auto border-t" style={{ borderColor: "var(--line)" }}>
      <div className="mx-auto flex max-w-[1680px] flex-col gap-4 px-4 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex items-center gap-2.5">
          <Brandmark className="h-6 w-6 text-ink-mute" />
          <p className="text-xs text-ink-mute">
            Every number from a real public source. Every model claim shipped with a{" "}
            <Link href="/receipts" className="text-airglow">
              validation receipt
            </Link>
            .
          </p>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-mute">
          <Link href="/ledger" className="hover:text-ink-soft">Intervention Ledger</Link>
          <Link href="/receipts" className="hover:text-ink-soft">Receipts</Link>
          <Link href="/about-data" className="hover:text-ink-soft">Data &amp; sources</Link>
          <Link href="/pitch" className="hover:text-ink-soft">Pitch</Link>
        </nav>
      </div>
    </footer>
  );
}

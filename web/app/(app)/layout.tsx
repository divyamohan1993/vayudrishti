import { AppHeader } from "@/components/chrome/AppHeader";
import { AppFooter } from "@/components/chrome/AppFooter";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader />
      <main id="main" className="flex flex-1 flex-col">
        {children}
      </main>
      <AppFooter />
    </div>
  );
}

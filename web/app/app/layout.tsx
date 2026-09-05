import Link from "next/link";
import { Logo } from "@/components/landing/Logo";

const nav = [["Overview", "/app"], ["Clusters", "/app/clusters"], ["Flags", "/app/flags"], ["Minnesota", "/app/states/MN"], ["Methods", "/app/methods"]];
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 bg-[var(--bg)]/90 backdrop-blur border-b border-[var(--line)]">
        <div className="max-w-[1240px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-7">
            <Link href="/"><Logo size={28} withText /></Link>
            <nav className="hidden md:flex gap-5 text-[13px] text-[var(--ink-2)]">{nav.map(([n, h]) => <Link key={h} href={h} className="hover:text-[var(--ink)]">{n}</Link>)}</nav>
          </div>
          <span className="text-[11px] text-[var(--ink-3)]">Public data only · no PHI · human signs every action</span>
        </div>
      </header>
      <main className="max-w-[1240px] mx-auto px-6 py-8">{children}</main>
    </div>
  );
}

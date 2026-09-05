import Link from "next/link";
import { Logo } from "@/components/landing/Logo";
import { Footer } from "@/components/landing/Footer";
const nav = [["Overview", "/app"], ["Candidates", "/app/candidates"], ["Communities", "/app/clusters"], ["Indicators", "/app/flags"], ["Plazas", "/app/plazas"], ["Minnesota", "/app/states/MN"], ["Methods", "/app/methods"]];
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-20 bg-white" style={{ borderBottom: "1px solid var(--ink)" }}>
        <div className="max-w-[1280px] mx-auto px-6 h-14 flex items-center justify-between gap-6">
          <div className="flex items-center gap-8">
            <Link href="/"><Logo size={26} /></Link>
            <nav className="hidden lg:flex gap-6 text-[13px] text-[var(--ink-2)]">{nav.map(([n, h]) => <Link key={h} href={h} className="hover:text-[var(--ink)]">{n}</Link>)}</nav>
          </div>
          <form action="/app/search" className="flex items-center gap-2 flex-1 max-w-md">
            <input name="q" placeholder="Search NPI or provider name" className="w-full" style={{ padding: "7px 10px" }} />
            <button className="btn" style={{ padding: "8px 14px" }}>Search</button>
          </form>
          <span className="hidden xl:block text-[11px] text-[var(--ink-3)]">Indicators, not findings. A human signs every action.</span>
        </div>
      </header>
      <main className="max-w-[1280px] mx-auto px-6 py-8 w-full flex-1">{children}</main>
      <Footer />
    </div>
  );
}

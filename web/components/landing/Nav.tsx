"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Logo } from "./Logo";
import { SearchBox } from "@/components/app/SearchBox";
// One header for the whole site. The landing page shows its section links and a Console link; the console keeps the identical
// geometry and shows its own section links, with the provider search where the Console link was.
const landingLinks: [string, string][] = [["What We Do", "/#what"], ["Who We Serve", "/#who"], ["How It Works", "/#how"], ["Methods", "/app/methods"]];
const consoleLinks: [string, string][] = [["Overview", "/app"], ["Providers", "/app/candidates"], ["Networks", "/app/clusters"], ["Methods", "/app/methods"]];
export function Nav({ mode = "landing" }: { mode?: "landing" | "console" }) {
  const [open, setOpen] = useState(false);
  const path = usePathname() ?? "";
  const links = mode === "console" ? consoleLinks : landingLinks;
  const active = (h: string) => mode === "console" && (h === "/app" ? path === "/app" : path.startsWith(h) || (h === "/app/candidates" && (path.startsWith("/app/providers") || path.startsWith("/app/flags") || path.startsWith("/app/search"))) || (h === "/app/clusters" && path.startsWith("/app/plazas")));
  return (
    <header className="bg-white sticky top-0 z-30">
      <div className="max-w-[1860px] mx-auto px-6 md:px-[72px] h-[76px] md:h-[92px] flex items-center justify-between">
        <Link href="/" aria-label="Verity home"><Logo size={28} /></Link>
        <nav className="hidden md:flex items-center gap-10 text-[15px]" style={{ color: "var(--ink)" }}>
          {links.map(([n, h]) => <Link key={n} href={h} className={active(h) ? "font-semibold" : "hover:text-[var(--blue)]"} style={{ color: active(h) ? "var(--blue)" : "var(--ink)" }}>{n}</Link>)}
        </nav>
        {mode === "console"
          ? <div className="hidden md:flex items-center gap-3 text-[15px] w-[360px]"><div className="flex-1"><SearchBox /></div><span className="hidden lg:inline text-[11px] text-[var(--ink-3)] whitespace-nowrap">⌘K</span></div>
          : <div className="hidden md:flex items-center gap-8 text-[15px]"><Link href="/app" className="hover:text-[var(--blue)]">Console</Link></div>}
        <button className="md:hidden p-2" aria-label="Menu" onClick={() => setOpen(o => !o)}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">{open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}</svg></button>
      </div>
      {open && <div className="md:hidden px-6 pb-6 flex flex-col gap-4 text-[16px] bg-white" style={{ borderTop: "1px solid var(--line)" }}>
        {mode === "console" && <div className="pt-4"><SearchBox /></div>}
        {links.map(([n, h]) => <Link key={n} href={h} onClick={() => setOpen(false)} className="pt-4">{n}</Link>)}
        {mode === "landing" && <Link href="/app" className="pt-4">Console</Link>}
      </div>}
    </header>
  );
}

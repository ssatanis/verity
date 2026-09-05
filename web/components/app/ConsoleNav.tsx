"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/landing/Logo";
import { SearchBox } from "./SearchBox";
const nav = [["Overview", "/app"], ["Providers", "/app/candidates"], ["Networks", "/app/clusters"], ["Methods", "/app/methods"]];
export function ConsoleNav() {
  const path = usePathname(); const [open, setOpen] = useState(false);
  const active = (h: string) => (h === "/app" ? path === "/app" : path.startsWith(h) || (h === "/app/candidates" && (path.startsWith("/app/providers") || path.startsWith("/app/flags") || path.startsWith("/app/search"))) || (h === "/app/clusters" && path.startsWith("/app/plazas")));
  return (
    <header className="sticky top-0 z-30 bg-white" style={{ borderBottom: "2px solid var(--blue)" }}>
      <div className="max-w-[1280px] mx-auto px-4 md:px-6 h-14 flex items-center justify-between gap-4">
        <div className="flex items-center gap-8">
          <Link href="/"><Logo size={24} /></Link>
          <nav className="hidden md:flex gap-7 text-[14px]">{nav.map(([n, h]) => <Link key={h} href={h} className={active(h) ? "font-semibold" : "hover:text-[var(--blue)]"} style={{ color: active(h) ? "var(--blue)" : "var(--ink)" }}>{n}</Link>)}</nav>
        </div>
        <div className="flex-1 max-w-md hidden sm:block"><SearchBox /></div>
        <button className="md:hidden p-2" aria-label="Menu" onClick={() => setOpen(o => !o)}><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">{open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}</svg></button>
      </div>
      {open && <div className="md:hidden px-4 pb-4 flex flex-col gap-3 bg-white" style={{ borderTop: "1px solid var(--line)" }}><div className="pt-3 sm:hidden"><SearchBox /></div>{nav.map(([n, h]) => <Link key={h} href={h} onClick={() => setOpen(false)} className="pt-3 text-[15px]">{n}</Link>)}</div>}
    </header>
  );
}

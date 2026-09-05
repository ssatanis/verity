"use client";
import Link from "next/link";
import { useState } from "react";
import { Logo } from "./Logo";
const links = [["What We Do", "#what"], ["Who We Serve", "#who"], ["How It Works", "#how"], ["Methods", "/app/methods"]];
export function Nav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="bg-white sticky top-0 z-30">
      <div className="max-w-[1860px] mx-auto px-6 md:px-[72px] h-[76px] md:h-[92px] flex items-center justify-between">
        <Link href="/" aria-label="Verity home"><Logo size={28} /></Link>
        <nav className="hidden md:flex items-center gap-10 text-[15px]" style={{ color: "var(--ink)" }}>
          {links.map(([n, h]) => <a key={n} href={h} className="hover:text-[var(--blue)]">{n}</a>)}
        </nav>
        <div className="hidden md:flex items-center gap-8 text-[15px]"><Link href="/app" className="hover:text-[var(--blue)]">Console</Link></div>
        <button className="md:hidden p-2" aria-label="Menu" onClick={() => setOpen(o => !o)}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">{open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}</svg></button>
      </div>
      {open && <div className="md:hidden px-6 pb-6 flex flex-col gap-4 text-[16px] bg-white" style={{ borderTop: "1px solid var(--line)" }}>{links.map(([n, h]) => <a key={n} href={h} onClick={() => setOpen(false)} className="pt-4">{n}</a>)}<Link href="/app" className="pt-4">Console</Link></div>}
    </header>
  );
}

"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { Logo } from "./Logo";
import { SearchBox } from "@/components/app/SearchBox";
import { useScrolled, useScrollSpy } from "./Scroll";
// One header for the whole site. The landing page shows its section links and a Console link; the console keeps the identical
// geometry and shows its own section links, with the provider search where the Console link was. On the landing page the header
// tightens and takes a rule once the reader leaves the hero, and the section link for the section they are in is marked.
const landingLinks: [string, string][] = [["What We Do", "/#what"], ["Who We Serve", "/#who"], ["How It Works", "/#how"], ["Methods", "/app/methods"]];
const consoleLinks: [string, string][] = [["Overview", "/app"], ["Providers", "/app/candidates"], ["Networks", "/app/clusters"], ["Methods", "/app/methods"]];
// Only the sections that have a link in the header: the mark then stays on the last link the reader passed, rather
// than going out whenever they are in a section with no link of its own.
const SPY_IDS = ["what", "who", "how"];
export function Nav({ mode = "landing" }: { mode?: "landing" | "console" }) {
  const [open, setOpen] = useState(false);
  const path = usePathname() ?? "";
  const scrolled = useScrolled(24);
  const reduce = useReducedMotion();
  const links = mode === "console" ? consoleLinks : landingLinks;
  const onLanding = mode === "landing" && path === "/";
  const spy = useScrollSpy(onLanding ? SPY_IDS : [], 150);
  const active = (h: string) => mode === "console"
    ? (h === "/app" ? path === "/app" : path.startsWith(h) || (h === "/app/candidates" && (path.startsWith("/app/providers") || path.startsWith("/app/flags") || path.startsWith("/app/search"))) || (h === "/app/clusters" && path.startsWith("/app/plazas")))
    : onLanding && h.startsWith("/#") && h.slice(2) === spy;
  return (
    <motion.header
      className="bg-white sticky top-0 z-30"
      initial={false}
      animate={{ borderBottomColor: scrolled ? "var(--line)" : "rgba(217,221,227,0)", boxShadow: scrolled ? "0 1px 14px rgba(0,40,86,0.06)" : "0 0 0 rgba(0,0,0,0)" }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      style={{ borderBottomWidth: 1, borderBottomStyle: "solid" }}
    >
      {/* The header sits on the same grid as the page under it: the wide landing measure, or the console's 1280px column,
          so the logo and the search line up with the content rather than hugging the window. */}
      <div className={`${mode === "console" ? "max-w-[1280px] px-4 md:px-6" : "max-w-[1860px] px-6 md:px-[72px]"} mx-auto flex items-center justify-between nav-bar${scrolled ? " nav-bar-tight" : ""}`}>
        <Link href="/" aria-label="Verity home" className="shrink-0"><Logo size={28} /></Link>
        <nav className="hidden md:flex items-center gap-10 text-[15px]" style={{ color: "var(--ink)" }}>
          {links.map(([n, h]) => {
            const on = active(h);
            return (
              <Link key={n} href={h} className="relative py-1 transition-colors" style={{ color: on ? "var(--blue)" : "var(--ink)", fontWeight: on && mode === "console" ? 600 : 400 }}>
                {n}
                {on && <motion.span layoutId={`nav-underline-${mode}`} className="absolute left-0 right-0 -bottom-0.5" style={{ height: 1.5, background: "var(--blue)" }} transition={{ duration: reduce ? 0 : 0.35, ease: [0.22, 1, 0.36, 1] }} />}
              </Link>
            );
          })}
        </nav>
        {mode === "console"
          ? <div className="hidden md:flex items-center gap-3 text-[15px] w-[360px]"><div className="flex-1"><SearchBox /></div><span className="hidden lg:inline text-[11px] text-[var(--ink-3)] whitespace-nowrap">⌘K</span></div>
          : <div className="hidden md:flex items-center gap-8 text-[15px]"><Link href="/app" className="btn-arrow inline-flex items-center gap-2 hover:text-[var(--blue)] transition-colors">Console<span className="btn-arrow-glyph" aria-hidden>&rarr;</span></Link></div>}
        <button className="md:hidden p-2" aria-label="Menu" aria-expanded={open} onClick={() => setOpen(o => !o)}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">{open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}</svg></button>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div key="menu" className="md:hidden overflow-hidden bg-white" style={{ borderTop: "1px solid var(--line)" }}
            initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: reduce ? 0 : 0.32, ease: [0.22, 1, 0.36, 1] }}>
            <div className={`${mode === "console" ? "max-w-[1280px] px-4 md:px-6" : "max-w-[1860px] px-6 md:px-[72px]"} mx-auto pb-6 flex flex-col gap-4 text-[16px]`}>
              {mode === "console" && <div className="pt-4"><SearchBox /></div>}
              {links.map(([n, h]) => <Link key={n} href={h} onClick={() => setOpen(false)} className="pt-4">{n}</Link>)}
              {mode === "landing" && <Link href="/app" onClick={() => setOpen(false)} className="pt-4">Console</Link>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}

import Link from "next/link";
import { Logo } from "./Logo";
export function Nav() {
  return (
    <header className="max-w-[1160px] mx-auto px-6 md:px-10 h-[68px] flex items-center justify-between">
      <Link href="/" aria-label="Verity home"><Logo size={30} /></Link>
      <nav className="hidden md:flex items-center gap-8 text-[13px] text-[var(--ink-2)]">
        <Link href="#detectors" className="hover:text-[var(--ink)]">Detectors</Link>
        <Link href="#how" className="hover:text-[var(--ink)]">How it works</Link>
        <Link href="#buyers" className="hover:text-[var(--ink)]">For payers</Link>
        <Link href="/app/methods" className="hover:text-[var(--ink)]">Methods</Link>
        <Link href="/app" className="hover:text-[var(--ink)]">Console</Link>
      </nav>
      <a href="mailto:ss4497@cornell.edu?subject=Verity%20pilot" className="btn">Request a pilot</a>
    </header>
  );
}

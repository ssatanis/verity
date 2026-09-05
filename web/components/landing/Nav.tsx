import Link from "next/link";
import { Logo } from "./Logo";
export function Nav() {
  return (
    <header className="bg-white">
      <div className="max-w-[1860px] mx-auto px-8 md:px-[72px] h-[92px] flex items-center justify-between">
        <Link href="/" aria-label="Verity home"><Logo size={30} /></Link>
        <nav className="hidden md:flex items-center gap-10 text-[15px]" style={{ color: "var(--ink)" }}>
          <Link href="#what" className="hover:text-[var(--blue)]">What We Do</Link>
          <Link href="#who" className="hover:text-[var(--blue)]">Who We Serve</Link>
          <Link href="#how" className="hover:text-[var(--blue)]">How It Works</Link>
          <Link href="/app/methods" className="hover:text-[var(--blue)]">Methods</Link>
        </nav>
        <div className="flex items-center gap-8 text-[15px]">
          <Link href="/app/search" aria-label="Search" className="hidden md:inline-flex"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg></Link>
          <Link href="/app" className="hover:text-[var(--blue)]">Console Login</Link>
        </div>
      </div>
    </header>
  );
}

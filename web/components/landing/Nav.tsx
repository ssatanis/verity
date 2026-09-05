import Link from "next/link";
import { Logo } from "./Logo";

export function Nav() {
  return (
    <header className="flex items-center justify-between px-5 py-4">
      <div className="flex items-center gap-7">
        <Link href="/" aria-label="Verity home"><Logo /></Link>
        <nav className="hidden md:flex items-center gap-6 text-[13px] text-[var(--ink-2)]">
          <Link href="#solution" className="hover:text-[var(--ink)]">Solution</Link>
          <Link href="/app" className="hover:text-[var(--ink)]">Console</Link>
          <Link href="/app/methods" className="hover:text-[var(--ink)]">Methods</Link>
          <Link href="/app/states/MN" className="hover:text-[var(--ink)]">Show the math</Link>
        </nav>
      </div>
      <Link href="/app" className="btn-dark">Open console</Link>
    </header>
  );
}

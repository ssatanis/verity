import Link from "next/link";
import { Logo } from "./Logo";

export function Footer() {
  return (
    <footer className="footer">
      <div className="max-w-[1160px] mx-auto px-8 md:px-16 py-16">
        <div className="flex flex-col md:flex-row justify-between gap-12">
          <Logo size={34} light />
          <div className="grid grid-cols-2 gap-x-20 gap-y-3 text-[17px]">
            <div className="eyebrow mb-2">Main</div>
            <div className="eyebrow mb-2">Company</div>
            <Link href="/">Home</Link><Link href="/#contact">Contact</Link>
            <Link href="/#about">About</Link><Link href="/terms">Terms Conditions</Link>
            <Link href="/app">Console</Link><Link href="/privacy">Privacy Policy</Link>
            <Link href="/app/methods">Methods</Link><Link href="/security">Security</Link>
          </div>
        </div>
        <div className="rule mt-12 pt-6 flex flex-col md:flex-row justify-between gap-2 text-[13px]">
          <span>© Verity 2026, All Rights Reserved</span>
          <span>Sahaj Satani &amp; Rohan Sanghavi</span>
        </div>
      </div>
    </footer>
  );
}

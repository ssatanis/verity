import Link from "next/link";
import { Logo } from "./Logo";
export function Footer() {
  const cols = [["Main", [["Home", "/"], ["What We Do", "/#what"], ["Console", "/app"], ["Methods", "/app/methods"]]], ["Company", [["Contact", "mailto:ss4497@cornell.edu"], ["Terms Conditions", "/legal#terms"], ["Privacy Policy", "/legal#privacy"], ["Security", "/legal#security"]]]] as const;
  return (
    <footer className="footer">
      <div className="max-w-[1860px] mx-auto px-8 md:px-[72px] py-16">
        <div className="flex flex-col md:flex-row justify-between gap-12">
          <div><Logo size={26} light /><p className="text-[13px] mt-6 max-w-sm" style={{ color: "#c7d0dd" }}>Pre-payment provider integrity for health plans and Medicaid programs, built on public federal and state records.</p></div>
          <div className="flex gap-20">{cols.map(([h, items]) => <div key={h}><div className="text-[11px] uppercase tracking-[0.18em] mb-5" style={{ color: "#c7d0dd" }}>{h}</div><ul className="space-y-3 text-[14px]">{items.map(([n, href]) => <li key={n}><Link href={href}>{n}</Link></li>)}</ul></div>)}</div>
        </div>
        <div className="mt-14 pt-6 flex flex-col md:flex-row justify-between gap-3 text-[12px]" style={{ borderTop: "1px solid rgba(255,255,255,0.25)", color: "#c7d0dd" }}>
          <span>© Verity 2026, All Rights Reserved</span><span>Sahaj Satani &amp; Rohan Sanghavi</span>
        </div>
      </div>
    </footer>
  );
}

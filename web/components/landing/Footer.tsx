import Link from "next/link";
import { Logo } from "./Logo";
export function Footer({ narrow = false }: { narrow?: boolean } = {}) {
  const cols = [["Main", [["Home", "/"], ["What We Do", "/#what"], ["Console", "/app"], ["Methods", "/app/methods"]]], ["Company", [["Contact", "mailto:ss4497@cornell.edu"], ["Terms Conditions", "/legal#terms"], ["Privacy Policy", "/legal#privacy"], ["Security", "/legal#security"]]]] as const;
  return (
    <footer className="footer">
      <div className={`${narrow ? "max-w-[1280px] px-4 md:px-6" : "max-w-[1860px] px-8 md:px-[72px]"} mx-auto py-16`}>
        <div className="flex flex-col md:flex-row justify-between gap-12">
          <div><Logo size={26} light /><p className="text-[13px] mt-6 max-w-sm" style={{ color: "#c7d0dd" }}>Provider integrity for health plans and Medicaid programs.</p></div>
          <div className="flex gap-20">{cols.map(([h, items]) => <div key={h}><div className="text-[11px] uppercase tracking-[0.18em] mb-5" style={{ color: "#c7d0dd" }}>{h}</div><ul className="space-y-3 text-[14px]">{items.map(([n, href]) => <li key={n}><Link href={href}>{n}</Link></li>)}</ul></div>)}</div>
        </div>
        <div className="mt-14 pt-6 text-[12px]" style={{ borderTop: "1px solid rgba(255,255,255,0.25)", color: "#c7d0dd" }}>© Verity 2026, All Rights Reserved</div>
      </div>
    </footer>
  );
}

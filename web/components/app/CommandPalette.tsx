"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { titleCase } from "@/lib/labels";
type Hit = { npi: string; name: string; city?: string; state?: string; entity_type?: string; tier?: number | null; source: string };
const NAV = [["Home", "/", "Landing page"], ["Overview", "/app", "Tiers, map, top providers and networks"], ["Providers", "/app/candidates", "Every flagged provider, ranked"], ["Networks", "/app/clusters", "Groups of providers that belong together"], ["Addresses hosting many providers", "/app/plazas", "Office plazas and shared suites"], ["Paid after a list action", "/app/flags?detector=D3", "Detail view"], ["Hours per day", "/app/flags?detector=D2", "Detail view"], ["Methods", "/app/methods", "How the numbers are made"], ["Terms, privacy and security", "/legal", ""]];
export function CommandPalette() {
  const [open, setOpen] = useState(false); const [q, setQ] = useState(""); const [hits, setHits] = useState<Hit[]>([]); const [busy, setBusy] = useState(false); const [ix, setIx] = useState(0);
  const router = useRouter(); const input = useRef<HTMLInputElement>(null); const t = useRef<any>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(o => !o); } else if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => { if (open) { setTimeout(() => input.current?.focus(), 20); setQ(""); setHits([]); setIx(0); } }, [open]);
  useEffect(() => {
    if (t.current) clearTimeout(t.current); const term = q.trim(); if (term.length < 2) { setHits([]); return; }
    t.current = setTimeout(async () => { setBusy(true); try { const r = await fetch(`/api/search?q=${encodeURIComponent(term)}`); if (r.ok) { const j = await r.json(); setHits(j.hits ?? []); } else setHits([]); } catch { setHits([]); } setBusy(false); setIx(0); }, 200);
    return () => clearTimeout(t.current);
  }, [q]);
  const nav = NAV.filter(([n,, d]) => !q.trim() || `${n} ${d}`.toLowerCase().includes(q.trim().toLowerCase()));
  const items: { label: string; sub: string; href: string; tier?: number | null; kind: "nav" | "provider" }[] = [
    ...hits.map(h => ({ label: h.name || h.npi, sub: `${h.npi}, ${h.entity_type === "2" ? "organization" : "individual"}${h.city ? `, ${titleCase(h.city)}, ${h.state}` : h.state ? `, ${h.state}` : ""}${h.source === "nppes" ? ", national registry" : ""}`, href: `/app/providers/${h.npi}`, tier: h.tier, kind: "provider" as const })),
    ...(/^\d{10}$/.test(q.trim()) && !hits.some(h => h.npi === q.trim()) ? [{ label: `Open NPI ${q.trim()}`, sub: "Look up this number in the registry", href: `/app/providers/${q.trim()}`, kind: "provider" as const }] : []),
    ...nav.map(([n, h, d]) => ({ label: n, sub: d, href: h, kind: "nav" as const })),
  ];
  function go(i: number) { const it = items[i]; if (!it) return; setOpen(false); router.push(it.href); }
  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setIx(i => Math.min(items.length - 1, i + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setIx(i => Math.max(0, i - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); if (items.length) go(ix); else if (q.trim()) { setOpen(false); router.push(`/app/search?q=${encodeURIComponent(q.trim())}`); } }
  }
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh] px-4" style={{ background: "rgba(0,40,86,0.35)" }} onMouseDown={() => setOpen(false)}>
      <div className="w-full max-w-2xl bg-white" style={{ border: "1px solid var(--blue)", boxShadow: "0 24px 60px rgba(0,40,86,0.25)" }} onMouseDown={e => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-4" style={{ borderBottom: "1px solid var(--line)" }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: "var(--blue)" }}><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
          <input ref={input} value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKeyDown} placeholder="Search any NPI or provider, or jump to a page" className="flex-1 text-[16px] py-4" style={{ border: "none", padding: "16px 0" }} aria-label="Command palette" />
          <span className="text-[11px] text-[var(--ink-3)]">esc</span>
        </div>
        <div className="max-h-[60vh] overflow-y-auto">
          {busy && <div className="px-4 py-2 text-[12px] text-[var(--ink-3)]">Searching</div>}
          {items.map((it, i) => (
            <button key={it.href + i} onMouseEnter={() => setIx(i)} onClick={() => go(i)} className="w-full text-left px-4 py-3 flex items-center gap-3" style={{ background: i === ix ? "var(--accent-2)" : "transparent", borderTop: "1px solid var(--line)" }}>
              {it.kind === "provider" ? (it.tier ? <span className={`tier tier-${it.tier}`}>{it.tier}</span> : <span className="tier" style={{ borderColor: "var(--line)", color: "var(--ink-3)" }}>&nbsp;</span>) : <span className="serif text-[15px] w-[26px] text-center" style={{ color: "var(--blue)" }}>→</span>}
              <span className="flex-1"><span className="text-[14px]">{it.label}</span>{it.sub ? <span className="block text-[11.5px] text-[var(--ink-3)]">{it.sub}</span> : null}</span>
              {i === ix && <span className="text-[11px] text-[var(--ink-3)]">enter</span>}
            </button>
          ))}
        </div>
        <div className="px-4 py-2 text-[11px] text-[var(--ink-3)] flex gap-4" style={{ borderTop: "1px solid var(--line)" }}><span>↑↓ move</span><span>enter open</span><span>⌘K toggle</span></div>
      </div>
    </div>
  );
}

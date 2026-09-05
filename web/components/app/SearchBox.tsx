"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
type Hit = { npi: string; name: string; city?: string; state?: string; entity_type?: string; tier?: number | null; source: string };
export function SearchBox({ autoFocus = false, large = false }: { autoFocus?: boolean; large?: boolean }) {
  const [q, setQ] = useState(""); const [hits, setHits] = useState<Hit[]>([]); const [open, setOpen] = useState(false); const [busy, setBusy] = useState(false);
  const router = useRouter(); const box = useRef<HTMLDivElement>(null); const t = useRef<any>(null);
  useEffect(() => {
    if (t.current) clearTimeout(t.current);
    const term = q.trim(); if (term.length < 2) { setHits([]); return; }
    t.current = setTimeout(async () => {
      setBusy(true);
      try { const r = await fetch(`/api/search?q=${encodeURIComponent(term)}`); const j = await r.json(); setHits(j.hits ?? []); setOpen(true); } catch { setHits([]); }
      setBusy(false);
    }, 220);
    return () => clearTimeout(t.current);
  }, [q]);
  useEffect(() => { const h = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); }; document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);
  function go(e: React.FormEvent) { e.preventDefault(); const term = q.trim(); if (!term) return; if (/^\d{10}$/.test(term)) router.push(`/app/providers/${term}`); else router.push(`/app/search?q=${encodeURIComponent(term)}`); setOpen(false); }
  return (
    <div ref={box} className="relative w-full">
      <form onSubmit={go} className="flex items-center gap-2">
        <input value={q} onChange={e => setQ(e.target.value)} onFocus={() => hits.length && setOpen(true)} placeholder="Search any NPI or provider name" className="w-full" style={{ padding: large ? "14px 16px" : "7px 10px", fontSize: large ? 16 : 13 }} autoFocus={autoFocus} aria-label="Search providers" />
        <button className="btn" style={{ padding: large ? "14px 22px" : "8px 14px" }}>Search</button>
      </form>
      {open && (hits.length > 0 || busy) && (
        <div className="absolute left-0 right-0 top-full mt-1 bg-white z-40 max-h-[380px] overflow-y-auto" style={{ border: "1px solid var(--blue)" }}>
          {busy && !hits.length && <div className="px-3 py-2 text-[12px] text-[var(--ink-3)]">Searching</div>}
          {hits.map(h => (
            <button key={h.npi} type="button" onClick={() => { router.push(`/app/providers/${h.npi}`); setOpen(false); }} className="w-full text-left px-3 py-2 hover:bg-[var(--paper-2)] flex items-center justify-between gap-3" style={{ borderTop: "1px solid var(--line)" }}>
              <span><span className="text-[13px]">{h.name || h.npi}</span><span className="block text-[11px] text-[var(--ink-3)]">{h.npi} · {h.entity_type === "2" ? "organisation" : "individual"}{h.city ? ` · ${h.city}, ${h.state}` : h.state ? ` · ${h.state}` : ""}</span></span>
              {h.tier ? <span className={`tier tier-${h.tier}`}>{h.tier}</span> : <span className="text-[11px] text-[var(--ink-3)]">{h.source === "nppes" ? "no indicators" : ""}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

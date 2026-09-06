"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { titleCase } from "@/lib/labels";
type Hit = { npi: string; name: string; city?: string; state?: string; entity_type?: string; tier?: number | null; source: string };
// Provider search. Suggestions are debounced and every request supersedes the one before it, so a slow answer can never
// overwrite a newer one; the arrow keys, Enter and Escape all work, and on the search page the box starts from the query
// in the URL so what is typed and what is shown never drift apart.
function Box({ autoFocus = false, large = false }: { autoFocus?: boolean; large?: boolean }) {
  const params = useSearchParams();
  const urlQ = params?.get("q") ?? "";
  const [q, setQ] = useState(urlQ);
  const [hits, setHits] = useState<Hit[]>([]); const [open, setOpen] = useState(false); const [busy, setBusy] = useState(false); const [ix, setIx] = useState(-1);
  const router = useRouter(); const box = useRef<HTMLDivElement>(null); const input = useRef<HTMLInputElement>(null);
  const t = useRef<ReturnType<typeof setTimeout> | null>(null); const seq = useRef(0); const abort = useRef<AbortController | null>(null);
  // The URL is the source of truth: a back button, a suggestion click or a fresh search all put the box back in step.
  useEffect(() => { setQ(urlQ); }, [urlQ]);
  useEffect(() => {
    if (t.current) clearTimeout(t.current);
    const term = q.trim();
    if (term.length < 2) { setHits([]); setIx(-1); abort.current?.abort(); return; }
    t.current = setTimeout(() => {
      const mine = ++seq.current;
      abort.current?.abort();
      const ac = new AbortController(); abort.current = ac;
      setBusy(true);
      fetch(`/api/search?q=${encodeURIComponent(term)}`, { signal: ac.signal })
        .then(r => r.json())
        .then(j => { if (mine !== seq.current) return; setHits(j.hits ?? []); setIx(-1); setOpen(true); })
        .catch(() => { if (mine === seq.current) setHits([]); })
        .finally(() => { if (mine === seq.current) setBusy(false); });
    }, 200);
    return () => { if (t.current) clearTimeout(t.current); };
  }, [q]);
  useEffect(() => { const h = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); }; document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);
  const open1 = (npi: string) => { setOpen(false); setIx(-1); router.push(`/app/providers/${npi}`); };
  function go(e: React.FormEvent) {
    e.preventDefault();
    if (ix >= 0 && hits[ix]) return open1(hits[ix].npi);
    const term = q.trim(); if (!term) return;
    setOpen(false);
    if (/^\d{10}$/.test(term)) router.push(`/app/providers/${term}`); else router.push(`/app/search?q=${encodeURIComponent(term)}`);
  }
  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Escape") { setOpen(false); setIx(-1); input.current?.blur(); return; }
    if (!open || !hits.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setIx(i => (i + 1) % hits.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setIx(i => (i <= 0 ? hits.length - 1 : i - 1)); }
  }
  return (
    <div ref={box} className="relative w-full">
      <form onSubmit={go} className="flex items-center gap-2">
        <div className="relative flex-1">
          <input ref={input} value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKey} onFocus={() => hits.length && setOpen(true)}
            placeholder="Search any NPI or provider name" className="w-full" style={{ padding: large ? "14px 16px" : "7px 10px", fontSize: large ? 16 : 13 }}
            autoFocus={autoFocus} aria-label="Search providers" role="combobox" aria-expanded={open} aria-autocomplete="list" aria-controls="search-suggestions"
            aria-activedescendant={ix >= 0 && hits[ix] ? `search-hit-${hits[ix].npi}` : undefined} autoComplete="off" spellCheck={false} />
          {busy && <span aria-hidden className="absolute right-2 top-1/2 -translate-y-1/2 block" style={{ width: 10, height: 10, border: "1.5px solid var(--line)", borderTopColor: "var(--blue)", animation: "verity-spin .7s linear infinite" }} />}
        </div>
        <button className="btn" style={{ padding: large ? "14px 22px" : "8px 14px" }}>Search</button>
      </form>
      {open && (hits.length > 0 || busy) && (
        <div id="search-suggestions" role="listbox" className="absolute left-0 right-0 top-full mt-1 bg-white z-40 max-h-[380px] overflow-y-auto" style={{ border: "1px solid var(--blue)", boxShadow: "0 10px 28px rgba(0,40,86,0.10)" }}>
          {busy && !hits.length && <div className="px-3 py-2 text-[12px] text-[var(--ink-3)]">Searching</div>}
          {hits.map((h, i) => (
            <button key={h.npi} id={`search-hit-${h.npi}`} role="option" aria-selected={i === ix} type="button" onMouseEnter={() => setIx(i)} onClick={() => open1(h.npi)}
              className="w-full text-left px-3 py-2 flex items-center justify-between gap-3" style={{ borderTop: "1px solid var(--line)", background: i === ix ? "var(--accent-2)" : undefined }}>
              <span><span className="text-[13px]">{h.name || h.npi}</span><span className="block text-[11px] text-[var(--ink-3)]">{h.npi}, {h.entity_type === "2" ? "organization" : "individual"}{h.city ? `, ${titleCase(h.city)}, ${h.state}` : h.state ? `, ${h.state}` : ""}</span></span>
              {h.tier ? <span className={`tier tier-${h.tier}`}>{h.tier}</span> : <span className="text-[11px] text-[var(--ink-3)]">{h.source === "nppes" ? "no indicators" : ""}</span>}
            </button>
          ))}
          {!busy && hits.length > 0 && <div className="px-3 py-2 text-[11px] text-[var(--ink-3)]" style={{ borderTop: "1px solid var(--line)" }}>Enter to see every match for &ldquo;{q.trim()}&rdquo;</div>}
        </div>
      )}
    </div>
  );
}
export function SearchBox(props: { autoFocus?: boolean; large?: boolean }) {
  return <Suspense fallback={<div className="relative w-full"><input className="w-full" disabled placeholder="Search any NPI or provider name" style={{ padding: props.large ? "14px 16px" : "7px 10px", fontSize: props.large ? 16 : 13 }} aria-label="Search providers" /></div>}><Box {...props} /></Suspense>;
}

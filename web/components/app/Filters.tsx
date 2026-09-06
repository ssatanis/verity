"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, useTransition } from "react";
// Console filters. The URL stays the single source of truth, so a filtered view is shareable, survives a reload and works
// with the back button. The current query arrives as a prop from the server rather than through useSearchParams, which keeps
// these controls out of a Suspense boundary and hydrated with the rest of the page. A click reads as selected immediately
// while the server renders the new rows, and the view they filter dims until those rows arrive.
export type Chip = { key: string; value?: string; label: string; count?: number; title?: string; accent?: boolean; required?: boolean };
// `required` marks a chip whose group always has a selection, so clicking the active one does not drop back to a default.
export type Query = Record<string, string | undefined>;

const toParams = (q: Query) => { const p = new URLSearchParams(); for (const [k, v] of Object.entries(q)) if (v) p.set(k, v); return p; };
const patched = (q: Query, patch: Query) => { const p = toParams(q); for (const [k, v] of Object.entries(patch)) { if (v == null || v === "") p.delete(k); else p.set(k, v); } p.delete("page"); return p; };

export function Filters({ groups, query, path, resetTo, note }: { groups: { name: string; chips: Chip[] }[]; query: Query; path: string; resetTo?: string; note?: React.ReactNode }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const settled = toParams(query).toString();
  // The chip the reader just clicked reads as selected before the server answers; once the URL catches up the query string
  // the server sent is the only state left.
  const [aiming, setAiming] = useState<string | null>(null);
  useEffect(() => { setAiming(null); }, [settled]);
  const active = new URLSearchParams(pending && aiming !== null ? aiming : settled);

  const go = useCallback((patch: Query) => {
    const next = patched(query, patch);
    setAiming(next.toString());
    start(() => router.push(`${path}${next.toString() ? `?${next}` : ""}`, { scroll: false }));
  }, [query, path, router]);

  // The filtered view dims while the server renders, through a class on the shell rather than a re-render of the table.
  useEffect(() => {
    const el = document.querySelector("[data-filtered]");
    if (!el) return;
    el.classList.toggle("is-pending", pending);
    el.classList.toggle("is-settled", !pending);
  }, [pending]);

  const on = (c: Chip) => (c.value == null ? !active.get(c.key) : active.get(c.key) === c.value);
  const filtered = [...toParams(query).keys()].some(k => k !== "page");
  return (
    <div className="mt-6">
      <div className="flex flex-wrap gap-2 text-[12px] items-center" role="group" aria-busy={pending}>
        {groups.map((g, gi) => (
          <span key={g.name} className="contents">
            {gi > 0 && <span aria-hidden className="self-stretch w-px mx-2 my-1" style={{ background: "var(--line)" }} />}
            {g.chips.map((c, ci) => {
              const sel = on(c);
              return (
                // The index is part of the key: a group can hold both a "clear" chip and a valued chip on the same key.
                <button key={`${g.name}:${c.key}:${c.value ?? ""}:${ci}`} type="button" title={c.title} aria-pressed={sel}
                  onClick={() => { if (sel && c.required) return; go({ [c.key]: sel && c.value != null ? undefined : c.value }); }}
                  className={`tag ${sel ? (c.accent ? "tag-accent" : "tag-ink") : ""}`}>
                  {c.label}{c.count != null && <span className="opacity-60"> {c.count.toLocaleString()}</span>}
                </button>
              );
            })}
          </span>
        ))}
        {resetTo && filtered && <button type="button" onClick={() => { setAiming(""); start(() => router.push(resetTo, { scroll: false })); }} className="tag" title="Clear every filter">Clear all</button>}
        {pending && <span className="text-[11px] text-[var(--ink-3)] ml-1">updating</span>}
      </div>
      {note && <div className="text-[11.5px] text-[var(--ink-3)] mt-3">{note}</div>}
    </div>
  );
}

// Paging that keeps every other filter in the query string and does not throw the reader back to the top of the page.
export function Pager({ page, hasNext, query, path }: { page: number; hasNext: boolean; query: Query; path: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const go = (p: number) => { const next = toParams(query); next.delete("page"); if (p > 1) next.set("page", String(p)); start(() => router.push(`${path}${next.toString() ? `?${next}` : ""}`, { scroll: false })); };
  return (
    <div className="flex gap-4 mt-4 text-[12px] items-center">
      <button type="button" className="link disabled:opacity-40 disabled:no-underline" disabled={page <= 1 || pending} onClick={() => go(page - 1)}>Previous</button>
      <span className="text-[var(--ink-3)]">Page {page}</span>
      <button type="button" className="link disabled:opacity-40 disabled:no-underline" disabled={!hasNext || pending} onClick={() => go(page + 1)}>Next</button>
      {pending && <span className="text-[11px] text-[var(--ink-3)]">loading</span>}
    </div>
  );
}

"use client";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
// A hairline that runs under the header from the moment an internal link is clicked until the new route has rendered,
// so a navigation that waits on the database never looks like a dead click. Cleared by the pathname or query changing.
function Bar() {
  const path = usePathname();
  const params = useSearchParams();
  const [busy, setBusy] = useState(false);
  const key = `${path}?${params?.toString() ?? ""}`;
  const at = useRef(key);
  useEffect(() => { if (at.current !== key) { at.current = key; setBusy(false); } }, [key]);
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as HTMLElement)?.closest?.("a");
      if (!a) return;
      const href = a.getAttribute("href");
      if (!href || a.target === "_blank" || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("http")) return;
      const next = new URL(href, window.location.href);
      if (next.pathname === window.location.pathname && next.search === window.location.search) return;
      setBusy(true);
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);
  // A navigation that never resolves should not leave the bar running for ever.
  useEffect(() => { if (!busy) return; const t = setTimeout(() => setBusy(false), 12000); return () => clearTimeout(t); }, [busy]);
  return <div aria-hidden className="fixed top-0 left-0 right-0 z-50" style={{ height: 2, pointerEvents: "none" }}>{busy && <div className="loading-sweep" />}</div>;
}
export function RouteProgress() { return <Suspense fallback={null}><Bar /></Suspense>; }

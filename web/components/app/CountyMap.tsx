"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import * as topojson from "topojson-client";
import Link from "next/link";
import { money, titleCase } from "@/lib/labels";
import { Reasons } from "./Reasons";
type County = { county_fips: string; state: string; county_name: string; dollars_at_risk: number; n_clusters: number; n_providers_flagged: number; top_cluster_id: string | null; d1_dollars: number; d2_dollars: number; d3_dollars: number; top_score?: number };
// The county map. The county the reader has open lives in the query string, so the panel survives a reload, can be linked to,
// and closes with the back button; hovering highlights the county under the cursor and the tooltip follows it.
function CountyMapInner({ counties, height = 520 }: { counties: County[]; height?: number }) {
  const ref = useRef<SVGSVGElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [topo, setTopo] = useState<any>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [rows, setRows] = useState<any[] | null>(null);
  const [zoomed, setZoomed] = useState(false);
  // The open county is kept in the query string with the History API rather than a router navigation: the panel becomes
  // linkable and the back button closes it, without re-running the page's database queries on every click.
  const [selFips, setSelFips] = useState<string | null>(null);
  useEffect(() => {
    const read = () => setSelFips(new URLSearchParams(window.location.search).get("county"));
    read();
    window.addEventListener("popstate", read);
    return () => window.removeEventListener("popstate", read);
  }, []);
  useEffect(() => { import("us-atlas/counties-10m.json").then(m => setTopo(m.default ?? m)); }, []);
  const byFips = useMemo(() => new Map(counties.map(c => [c.county_fips.padStart(5, "0"), c])), [counties]);
  const max = useMemo(() => d3.max(counties, c => Number(c.dollars_at_risk)) || 1, [counties]);
  const sel = selFips ? byFips.get(selFips.padStart(5, "0")) ?? null : null;

  const select = useCallback((fips: string | null) => {
    const next = new URLSearchParams(window.location.search);
    if (fips) next.set("county", fips); else next.delete("county");
    const url = `${window.location.pathname}${next.toString() ? `?${next}` : ""}`;
    window.history.pushState(null, "", url);
    setSelFips(fips);
  }, []);

  useEffect(() => {
    if (!topo || !ref.current) return;
    const svg = d3.select(ref.current); svg.selectAll("*").remove();
    const width = 980;
    const feats0 = topojson.feature(topo, topo.objects.counties) as any;
    const projection = d3.geoAlbersUsa().scale(1300).translate([487.5, 305]);
    const path2 = d3.geoPath(projection);
    const color = d3.scaleSequentialLog([1e4, max], t => d3.interpolateRgb("#dfe6f0", "#002856")(t));
    const g = svg.attr("viewBox", `0 0 ${width} 610`).append("g");
    g.selectAll("path").data(feats0.features).join("path")
      .attr("d", path2 as any).attr("fill", (d: any) => { const c = byFips.get(d.id); return c && Number(c.dollars_at_risk) > 0 ? color(Number(c.dollars_at_risk)) : "#f5f5f5"; })
      .attr("stroke", (d: any) => (byFips.get(d.id) ? "#ffffff" : "none")).attr("stroke-width", 0.3).style("cursor", (d: any) => (byFips.get(d.id) ? "pointer" : "default"))
      .on("mouseenter", (_: any, d: any) => setHover(d.id))
      .on("mousemove", (e: any) => { const r = wrap.current?.getBoundingClientRect(); if (r) setTip({ x: e.clientX - r.left, y: e.clientY - r.top }); })
      .on("mouseleave", () => setHover(null))
      .on("click", (_: any, d: any) => { if (byFips.get(d.id)) select(d.id); });
    g.append("path").datum(topojson.mesh(topo, topo.objects.states, (a: any, b: any) => a !== b)).attr("fill", "none").attr("stroke", "#ffffff").attr("stroke-width", 0.8).attr("d", path2 as any);
    // The county under the cursor, and the one the reader has open, are outlined on their own layer so the outline is never
    // painted over by a neighbouring county.
    g.append("path").attr("class", "hover-outline").attr("fill", "none").attr("stroke", "#002856").attr("stroke-width", 1.2).attr("pointer-events", "none");
    g.append("path").attr("class", "sel-outline").attr("fill", "none").attr("stroke", "#002856").attr("stroke-width", 2).attr("pointer-events", "none");
    (svg.node() as any).__feats = feats0; (svg.node() as any).__path = path2;
    const zoom = d3.zoom<SVGSVGElement, unknown>().scaleExtent([1, 8]).on("zoom", e => { g.attr("transform", e.transform); setZoomed(e.transform.k > 1.02); });
    zoomRef.current = zoom;
    svg.call(zoom as any).on("dblclick.zoom", null);
  }, [topo, byFips, max, select]);

  // Outlines are redrawn on their own, without rebuilding the whole map on every mouse move.
  useEffect(() => {
    const node = ref.current as any; if (!node?.__feats) return;
    const svg = d3.select(ref.current);
    const draw = (cls: string, id: string | null) => {
      const f = id ? node.__feats.features.find((x: any) => x.id === String(id).padStart(5, "0")) : null;
      svg.select(`.${cls}`).attr("d", f ? node.__path(f) : null);
    };
    draw("hover-outline", hover); draw("sel-outline", selFips);
  }, [hover, selFips, topo]);

  useEffect(() => {
    if (!sel) { setRows(null); return; }
    setRows(null);
    const ac = new AbortController();
    fetch(`/api/county?fips=${sel.county_fips}`, { signal: ac.signal }).then(r => r.json()).then(j => setRows(j.rows ?? [])).catch(() => { if (!ac.signal.aborted) setRows([]); });
    return () => ac.abort();
  }, [sel?.county_fips]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && selFips) select(null); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [selFips, select]);

  const resetZoom = () => { const svg = d3.select(ref.current); if (zoomRef.current) svg.transition().duration(450).call(zoomRef.current.transform as any, d3.zoomIdentity); };
  const h = hover ? byFips.get(hover) : null;
  return (
    <div ref={wrap} className="relative" style={{ height }}>
      <svg ref={ref} className="w-full h-full" role="img" aria-label="Dollars at stake by county" />
      {!topo && <div className="absolute inset-0 grid place-items-center text-[12px] text-[var(--ink-3)]">Drawing the map</div>}
      <div className="absolute left-3 bottom-3 text-[11px] text-[var(--ink-3)] bg-white/90 px-2 py-1">Dollars at stake by county. Darker is more. Scroll to zoom, click a county for details.</div>
      {zoomed && <button onClick={resetZoom} className="absolute right-3 bottom-3 tag bg-white z-10">Reset zoom</button>}
      {h && !sel && (
        <div className="absolute bg-white px-3 py-2 text-[12px] pointer-events-none z-10" style={{ border: "1px solid var(--blue)", left: Math.min(tip.x + 14, 720), top: Math.max(8, tip.y - 44) }}>
          <b>{titleCase(h.county_name)}, {h.state}</b>, {money(h.dollars_at_risk)}, {h.n_providers_flagged} providers, {h.n_clusters} networks
        </div>
      )}
      {sel && (
        <aside className="absolute top-0 right-0 bottom-0 w-full sm:w-[380px] bg-white overflow-y-auto z-20" style={{ borderLeft: "1px solid var(--blue)", boxShadow: "-8px 0 24px rgba(0,40,86,0.08)", animation: "verity-slide-in .28s cubic-bezier(.22,1,.36,1) both" }}>
          <div className="p-5">
            <div className="flex items-start justify-between gap-3"><div><div className="eyebrow">County</div><h3 className="serif text-[28px] leading-tight" style={{ color: "var(--blue)" }}>{titleCase(sel.county_name)}, {sel.state}</h3></div><button onClick={() => select(null)} className="text-[12px] link" title="Escape">Close</button></div>
            <div className="grid grid-cols-2 gap-px mt-4" style={{ background: "var(--line)", border: "1px solid var(--line)" }}>
              {[["At stake", money(sel.dollars_at_risk)], ["Providers flagged", String(sel.n_providers_flagged)], ["Networks", String(sel.n_clusters)], ["Paid after a list action", money(sel.d3_dollars)], ["Impossible hours", money(sel.d2_dollars)], ["Networks, Medicaid 2024", money(sel.d1_dollars)]].map(([l, v]) => <div key={l} className="p-3 bg-white"><div className="text-[10.5px] text-[var(--ink-3)]">{l}</div><div className="serif text-[22px]" style={{ color: "var(--blue)" }}>{v}</div></div>)}
            </div>
            <div className="mt-4"><div className="eyebrow mb-2">Top providers here</div>
              {rows === null && <div className="text-[12px] text-[var(--ink-3)]">Loading</div>}
              {rows?.length === 0 && <div className="text-[12px] text-[var(--ink-3)]">No ranked providers in this county.</div>}
              <div className="rows-in">{rows?.map((r: any) => <Link key={r.npi} href={`/app/providers/${r.npi}`} className="block py-2 rule"><div className="flex items-center gap-2 text-[13px]"><span className={`tier tier-${r.tier}`}>{r.tier}</span><span className="link">{r.name || r.npi}</span><span className="ml-auto text-[12px]">{money(r.dollars_at_risk)}</span></div><div className="text-[11px] text-[var(--ink-3)] mt-1"><Reasons text={r.reasons} compact max={2} /></div></Link>)}</div>
            </div>
            {sel.top_cluster_id && <Link href={`/app/clusters/${sel.top_cluster_id}`} className="btn mt-4 w-full justify-center" style={{ padding: "10px 14px" }}>Open the top network here</Link>}
            <Link href={`/app/candidates?state=${sel.state}`} className="btn btn-ghost mt-2 w-full justify-center" style={{ padding: "10px 14px" }}>All providers in {sel.state}</Link>
          </div>
        </aside>
      )}
    </div>
  );
}

export function CountyMap(props: { counties: County[]; height?: number }) { return <CountyMapInner {...props} />; }

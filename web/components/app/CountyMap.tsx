"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import * as topojson from "topojson-client";
import Link from "next/link";
import { money } from "@/lib/labels";
type County = { county_fips: string; state: string; county_name: string; dollars_at_risk: number; n_clusters: number; n_providers_flagged: number; top_cluster_id: string | null; d1_dollars: number; d2_dollars: number; d3_dollars: number; top_score?: number };
export function CountyMap({ counties, height = 520 }: { counties: County[]; height?: number }) {
  const ref = useRef<SVGSVGElement>(null);
  const [topo, setTopo] = useState<any>(null);
  const [sel, setSel] = useState<County | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [rows, setRows] = useState<any[] | null>(null);
  useEffect(() => { import("us-atlas/counties-10m.json").then(m => setTopo(m.default ?? m)); }, []);
  const byFips = useMemo(() => new Map(counties.map(c => [c.county_fips.padStart(5, "0"), c])), [counties]);
  const max = useMemo(() => d3.max(counties, c => Number(c.dollars_at_risk)) || 1, [counties]);
  useEffect(() => {
    if (!topo || !ref.current) return;
    const svg = d3.select(ref.current); svg.selectAll("*").remove();
    const width = 980;
    const feats0 = topojson.feature(topo, topo.objects.counties) as any;
    const projection = d3.geoAlbersUsa().scale(1300).translate([487.5, 305]);
    const path = d3.geoPath(projection);
    const color = d3.scaleSequentialLog([1e4, max], t => d3.interpolateRgb("#dfe6f0", "#002856")(t));
    const g = svg.attr("viewBox", `0 0 ${width} 610`).append("g");
    g.selectAll("path").data(feats0.features).join("path")
      .attr("d", path as any).attr("fill", (d: any) => { const c = byFips.get(d.id); return c && Number(c.dollars_at_risk) > 0 ? color(Number(c.dollars_at_risk)) : "#f5f5f5"; })
      .attr("stroke", (d: any) => (byFips.get(d.id) ? "#ffffff" : "none")).attr("stroke-width", 0.3).style("cursor", (d: any) => (byFips.get(d.id) ? "pointer" : "default"))
      .on("mouseenter", (_: any, d: any) => setHover(d.id)).on("mouseleave", () => setHover(null))
      .on("click", (_: any, d: any) => { const c = byFips.get(d.id); if (c) setSel(c); });
    g.append("path").datum(topojson.mesh(topo, topo.objects.states, (a: any, b: any) => a !== b)).attr("fill", "none").attr("stroke", "#ffffff").attr("stroke-width", 0.8).attr("d", path as any);
    const zoom = d3.zoom<SVGSVGElement, unknown>().scaleExtent([1, 8]).on("zoom", e => g.attr("transform", e.transform)); svg.call(zoom as any);
  }, [topo, byFips, max]);
  useEffect(() => {
    if (!sel) { setRows(null); return; }
    setRows(null);
    fetch(`/api/county?fips=${sel.county_fips}`).then(r => r.json()).then(j => setRows(j.rows ?? [])).catch(() => setRows([]));
  }, [sel]);
  const h = hover ? byFips.get(hover) : null;
  return (
    <div className="relative" style={{ height }}>
      <svg ref={ref} className="w-full h-full" />
      <div className="absolute left-3 bottom-3 text-[11px] text-[var(--ink-3)] bg-white/90 px-2 py-1">Dollars at stake by county. Darker is more. Scroll to zoom, click a county for details.</div>
      {h && !sel && <div className="absolute left-3 top-3 bg-white px-3 py-2 text-[12px]" style={{ border: "1px solid var(--blue)" }}><b>{h.county_name}, {h.state}</b>, {money(h.dollars_at_risk)}, {h.n_providers_flagged} providers, {h.n_clusters} networks</div>}
      {sel && (
        <aside className="absolute top-0 right-0 bottom-0 w-full sm:w-[380px] bg-white overflow-y-auto" style={{ borderLeft: "1px solid var(--blue)", boxShadow: "-8px 0 24px rgba(0,40,86,0.08)" }}>
          <div className="p-5">
            <div className="flex items-start justify-between gap-3"><div><div className="eyebrow">County</div><h3 className="serif text-[28px] leading-tight" style={{ color: "var(--blue)" }}>{sel.county_name}, {sel.state}</h3></div><button onClick={() => setSel(null)} className="text-[12px] link">Close</button></div>
            <div className="grid grid-cols-2 gap-px mt-4" style={{ background: "var(--line)", border: "1px solid var(--line)" }}>
              {[["At stake", money(sel.dollars_at_risk)], ["Providers flagged", String(sel.n_providers_flagged)], ["Networks", String(sel.n_clusters)], ["Paid after a list action", money(sel.d3_dollars)], ["Impossible hours", money(sel.d2_dollars)], ["Networks, Medicaid 2024", money(sel.d1_dollars)]].map(([l, v]) => <div key={l} className="p-3 bg-white"><div className="text-[10.5px] text-[var(--ink-3)]">{l}</div><div className="serif text-[22px]" style={{ color: "var(--blue)" }}>{v}</div></div>)}
            </div>
            <div className="mt-4"><div className="eyebrow mb-2">Top providers here</div>
              {rows === null && <div className="text-[12px] text-[var(--ink-3)]">Loading</div>}
              {rows?.length === 0 && <div className="text-[12px] text-[var(--ink-3)]">No ranked providers in this county.</div>}
              {rows?.map((r: any) => <Link key={r.npi} href={`/app/providers/${r.npi}`} className="block py-2 rule"><div className="flex items-center gap-2 text-[13px]"><span className={`tier tier-${r.tier}`}>{r.tier}</span><span className="link">{r.name || r.npi}</span><span className="ml-auto text-[12px]">{money(r.dollars_at_risk)}</span></div><div className="text-[11px] text-[var(--ink-3)] line-clamp-2">{r.reasons}</div></Link>)}
            </div>
            {sel.top_cluster_id && <Link href={`/app/clusters/${sel.top_cluster_id}`} className="btn mt-4 w-full justify-center" style={{ padding: "10px 14px" }}>Open the top network here</Link>}
            <Link href={`/app/candidates?state=${sel.state}`} className="btn btn-ghost mt-2 w-full justify-center" style={{ padding: "10px 14px" }}>All providers in {sel.state}</Link>
          </div>
        </aside>
      )}
    </div>
  );
}

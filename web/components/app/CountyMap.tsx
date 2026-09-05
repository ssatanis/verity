"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import * as topojson from "topojson-client";
import Link from "next/link";

type County = { county_fips: string; state: string; county_name: string; dollars_at_risk: number; n_clusters: number; n_providers_flagged: number; top_cluster_id: string | null; d1_dollars: number; d2_dollars: number; d3_dollars: number };
export function CountyMap({ counties, height = 520 }: { counties: County[]; height?: number }) {
  const ref = useRef<SVGSVGElement>(null);
  const [topo, setTopo] = useState<any>(null);
  const [tip, setTip] = useState<{ x: number; y: number; c: County } | null>(null);
  useEffect(() => { import("us-atlas/counties-10m.json").then(m => setTopo(m.default ?? m)); }, []);
  const byFips = useMemo(() => new Map(counties.map(c => [c.county_fips.padStart(5, "0"), c])), [counties]);
  const max = useMemo(() => d3.max(counties, c => Number(c.dollars_at_risk)) || 1, [counties]);
  useEffect(() => {
    if (!topo || !ref.current) return;
    const svg = d3.select(ref.current); svg.selectAll("*").remove();
    const width = 980;
    const feats0 = topojson.feature(topo, topo.objects.counties) as any;
    // us-atlas ships counties-10m in lon/lat here (bbox -179..180), so project with Albers USA; if a build ever ships it pre-projected, draw as-is
    const b = d3.geoBounds(feats0); const isDegrees = b[0][0] >= -181 && b[1][0] <= 181 && b[1][1] <= 91;
    const path = isDegrees ? d3.geoPath(d3.geoAlbersUsa().fitSize([width, 610], feats0)) : d3.geoPath();
    const color = d3.scaleSequentialLog([1e4, max], t => d3.interpolateRgb("#dfe6f0", "#002856")(t));
    const g = svg.append("g");
    const feats = feats0;
    g.append("g").selectAll("path").data(feats.features).join("path")
      .attr("d", path as any).attr("fill", (d: any) => { const c = byFips.get(d.id); return c && Number(c.dollars_at_risk) > 0 ? color(Number(c.dollars_at_risk)) : "#f5f5f5"; })
      .attr("stroke", "#fff").attr("stroke-width", 0.3)
      .on("mousemove", (ev: any, d: any) => { const c = byFips.get(d.id); if (c) setTip({ x: ev.offsetX, y: ev.offsetY, c }); })
      .on("mouseleave", () => setTip(null));
    g.append("path").datum(topojson.mesh(topo, topo.objects.states, (a: any, b: any) => a !== b)).attr("fill", "none").attr("stroke", "#ffffff").attr("stroke-width", 0.6).attr("d", path as any);
    const zoom = d3.zoom<SVGSVGElement, unknown>().scaleExtent([1, 8]).on("zoom", (ev) => g.attr("transform", ev.transform));
    svg.call(zoom as any);
    svg.attr("viewBox", `0 0 ${width} 610`);
  }, [topo, byFips, max]);
  return (
    <div className="relative">
      <svg ref={ref} className="w-full" style={{ height }} />
      {tip && (
        <div className="absolute pointer-events-none bg-white border border-[var(--ink)] p-3 text-[12px]" style={{ left: tip.x + 12, top: tip.y + 12 }}>
          <div className="font-medium">{tip.c.county_name}, {tip.c.state}</div>
          <div className="text-[var(--ink-3)]">at risk ${(Number(tip.c.dollars_at_risk) / 1e6).toFixed(2)}M · {tip.c.n_clusters} communities · {tip.c.n_providers_flagged} flagged NPIs</div>
          <div className="text-[var(--ink-3)]">D1 ${(Number(tip.c.d1_dollars) / 1e6).toFixed(1)}M · D2 ${(Number(tip.c.d2_dollars) / 1e6).toFixed(1)}M · D3 ${(Number(tip.c.d3_dollars) / 1e6).toFixed(1)}M</div>
          {tip.c.top_cluster_id && <div className="mt-1 text-[var(--blue)]">{tip.c.top_cluster_id}</div>}
        </div>
      )}
      <div className="absolute bottom-2 left-2 text-[10px] text-[var(--ink-3)]">Dollars at risk by county (log scale). Scroll to zoom, hover for detail.</div>
      {!topo && <div className="absolute inset-0 grid place-items-center text-[12px] text-[var(--ink-3)]">Loading counties</div>}
    </div>
  );
}

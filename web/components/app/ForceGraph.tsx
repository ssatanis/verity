"use client";
import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";

// three-colour palette: flag blue, black, white; node kinds are told apart by fill, opacity and outline
const COLOR: Record<string, string> = { provider: "#002856", person: "#000000", org: "#ffffff", addr: "#7f93ab", unit: "#7f93ab", phone: "#808080", fax: "#808080", ao: "#ffffff", mail: "#7f93ab", ein: "#000000" };
const STROKE: Record<string, string> = { provider: "#002856", person: "#000000", org: "#002856", addr: "#7f93ab", unit: "#002856", phone: "#808080", fax: "#808080", ao: "#000000", mail: "#7f93ab", ein: "#002856" };
export function ForceGraph({ graph, height = 520 }: { graph: { nodes: any[]; edges: any[] }; height?: number }) {
  const ref = useRef<SVGSVGElement>(null);
  const [sel, setSel] = useState<any>(null);
  useEffect(() => {
    if (!ref.current || !graph?.nodes?.length) return;
    const svg = d3.select(ref.current); svg.selectAll("*").remove();
    const width = ref.current.clientWidth || 900;
    const nodes = graph.nodes.map(n => ({ ...n })); const ids = new Set(nodes.map(n => n.id));
    const links = graph.edges.filter(e => ids.has(e.source) && ids.has(e.target)).map(e => ({ ...e }));
    const sim = d3.forceSimulation(nodes as any).force("link", d3.forceLink(links as any).id((d: any) => d.id).distance((l: any) => (l.weight ? 40 + 60 * (1 - Math.min(l.weight, 1)) : 120)).strength((l: any) => Math.max(0.05, Math.min(l.weight ?? 0.5, 1))))
      .force("charge", d3.forceManyBody().strength(-140)).force("center", d3.forceCenter(width / 2, height / 2)).force("collide", d3.forceCollide(16));
    const g = svg.append("g");
    const link = g.append("g").selectAll("line").data(links).join("line").attr("stroke", "#c7d0dd").attr("stroke-width", (l: any) => 0.6 + 2 * (l.weight ?? 0.3)).attr("stroke-dasharray", (l: any) => (l.weight === 0 ? "3 3" : null));
    const node = g.append("g").selectAll("g").data(nodes).join("g").style("cursor", "pointer").on("click", (_: any, d: any) => setSel(d))
      .call(d3.drag<any, any>().on("start", (ev, d) => { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }).on("drag", (ev, d) => { d.fx = ev.x; d.fy = ev.y; }).on("end", (ev, d) => { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }) as any);
    node.append("circle").attr("r", (d: any) => (d.kind === "provider" ? 9 : d.hub ? 7 : 5)).attr("fill", (d: any) => (d.hub ? "#fff" : COLOR[d.kind] ?? "#808080")).attr("stroke", (d: any) => (d.labels?.length || d.owner_labels?.length ? "#000000" : d.hub ? "#808080" : STROKE[d.kind] ?? "#808080")).attr("stroke-width", (d: any) => (d.labels?.length || d.owner_labels?.length ? 3 : 1.2)).attr("stroke-dasharray", (d: any) => (d.labels?.length || d.owner_labels?.length ? "2 1.5" : null));
    node.append("text").text((d: any) => (d.kind === "provider" ? (d.label || "").slice(0, 26) : d.kind === "person" || d.kind === "org" ? (d.label || "").slice(0, 22) : "")).attr("x", 11).attr("y", 4).attr("font-size", 9).attr("fill", "#333333");
    sim.on("tick", () => { link.attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y).attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y); node.attr("transform", (d: any) => `translate(${d.x},${d.y})`); });
    svg.call(d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.3, 4]).on("zoom", ev => g.attr("transform", ev.transform)) as any);
    return () => { sim.stop(); };
  }, [graph, height]);
  return (
    <div className="relative">
      <svg ref={ref} className="w-full" style={{ height }} />
      <div className="absolute top-2 left-2 flex gap-3 text-[10px] text-[var(--ink-3)] bg-white/90 px-2 py-1">
        {Object.entries({ provider: "provider", person: "owner (person)", org: "owner (org)", addr: "address", phone: "phone", ein: "EIN" }).map(([k, v]) => <span key={k} className="flex items-center gap-1"><span className="w-2 h-2 inline-block" style={{ background: COLOR[k], border: `1px solid ${STROKE[k]}` }} />{v}</span>)}
        <span className="flex items-center gap-1"><span className="w-2 h-2 inline-block border-2 border-dashed border-black" />on a list</span>
        <span>dashed: hub held out</span>
      </div>
      {sel && (
        <div className="absolute right-2 top-2 bg-white border border-[var(--ink)] p-3 text-[12px] max-w-xs">
          <div className="font-medium">{sel.label || sel.id}</div>
          <div className="text-[var(--ink-3)]">{sel.kind}{sel.ptype ? ` · ${sel.ptype}` : ""}{sel.city ? ` · ${sel.city}, ${sel.state}` : ""}{sel.inc_date ? ` · inc ${sel.inc_date}` : ""}{sel.prov_degree ? ` · ${sel.prov_degree} providers` : ""}</div>
          {sel.labels?.length ? <div className="text-[var(--danger)] mt-1">{sel.labels.join(", ")}</div> : null}
          {sel.owner_labels?.length ? <div className="text-[var(--danger)] mt-1">{sel.owner_labels.map((l: any) => l.join(" ")).join("; ")}</div> : null}
          {sel.npi && <a className="link mt-1 inline-block" href={`/app/providers/${sel.npi}`}>NPI {sel.npi}</a>}
        </div>
      )}
    </div>
  );
}

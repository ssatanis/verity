import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { ForceGraph } from "@/components/app/ForceGraph";
import { PacketPanel } from "@/components/app/PacketPanel";
import { AskCase } from "@/components/app/AskCase";
import { money } from "@/lib/labels";
export const revalidate = 60;
export default async function Cluster({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; const sb = publicClient();
  const [{ data: c }, { data: members }, { data: packets }] = await Promise.all([
    sb.from("clusters").select("*").eq("id", id).maybeSingle(),
    sb.from("cluster_members").select("*").eq("cluster_id", id).order("medicaid_2024", { ascending: false }),
    sb.from("packets").select("id,status,packet,created_at,model").eq("subject_id", id).order("created_at", { ascending: false }).limit(1),
  ]);
  if (!c) return <div className="card-2 p-6">Network not found.</div>;
  const f = (typeof c.features === "string" ? JSON.parse(c.features) : c.features) ?? {};
  const graph = typeof c.graph === "string" ? JSON.parse(c.graph) : c.graph;
  const facts: string[] = Array.isArray(f.facts) && f.facts.length ? f.facts : String(c.summary ?? "").split(". ").filter(Boolean).map((s: string) => s.replace(/\.$/, "") + ".");
  const feats: [string, any][] = [["Providers in the network", c.n_providers], ["Separate companies", f.n_distinct_orgs], ["Companies formed within one 90-day window", f.burst_90], ["Formed in 2021 or later", f.n_new], ["Most providers at one building", f.addr_share], ["Most providers in one suite", f.unit_share], ["Owners on three or more providers", f.owner_multi], ["Most providers under one owner", f.max_owner_degree], ["Providers sharing a phone number", f.phone_share], ["Providers sharing an official", f.ao_share], ["Providers at a revoked or excluded company's address", f.excluded_link], ["Providers revoked by Medicare", f.revoked_nbr], ["Providers terminated by a state", f.medicaid_term_nbr], ["Providers on a state exclusion list", f.state_excl], ["Share of providers in a known chain", f.chain_share != null ? `${Math.round(Number(f.chain_share) * 100)}%` : null], ["Providers per 10,000 beneficiaries in the county", f.sat_per_10k != null ? Number(f.sat_per_10k).toFixed(1) : null]];
  return (
    <div>
      <Link href="/app/clusters" className="eyebrow">Provider networks</Link>
      <div className="flex flex-col md:flex-row items-start justify-between gap-6 mt-2 mb-6">
        <div className="max-w-3xl"><h1 className="display serif text-[40px] md:text-[48px]">{c.id} <span className="text-[var(--ink-3)]">{c.city}</span></h1><p className="serif text-[22px] mt-3" style={{ color: "var(--blue)" }}>{c.summary}</p>
          <ul className="mt-4 space-y-2 text-[14px] leading-6">{facts.map((x, i) => <li key={i} className="flex gap-3"><span className="serif text-[16px] shrink-0" style={{ color: "var(--blue)" }}>{String(i + 1).padStart(2, "0")}</span><span>{x}</span></li>)}</ul>
          <div className="flex gap-2 mt-4 text-[11px]">{c.eligible ? <span className="tag tag-accent">ranked</span> : <span className="tag">not ranked</span>}{c.chain_or_pe ? <span className="tag">chain or platform</span> : null}<span className="tag">{c.state}</span></div></div>
        <div className="kpi min-w-[240px] md:text-right"><div className="eyebrow">Network score · ranked {c.rank}</div><div className="serif text-[44px]" style={{ color: "var(--blue)" }}>{Number(c.score).toFixed(0)}<span className="text-[18px] text-[var(--ink-3)]"> of 100</span></div><div className="text-[11px] text-[var(--ink-3)] mt-1">{money(c.dollars_at_risk)} Medicaid 2024 · {money(c.dollars_medicare)} Medicare 2023</div></div>
      </div>
      <div className="card p-2 mb-6"><ForceGraph graph={graph} /></div>
      <div className="grid md:grid-cols-[1fr_1.4fr] gap-6">
        <div className="space-y-6">
          <div className="card p-5"><h2 className="serif text-[24px] mb-3">By the numbers</h2>
            <table className="table"><tbody>{feats.filter(([, v]) => v != null && v !== 0 && v !== "0%").map(([k, v]) => <tr key={k}><td className="text-[var(--ink-2)]">{k}</td><td className="text-right">{String(v)}</td></tr>)}</tbody></table>
            {f.burst_90_span && <div className="text-[11px] text-[var(--ink-3)] mt-2">Formation window {f.burst_90_span[0]} to {f.burst_90_span[1]}</div>}
          </div>
          <PacketPanel subjectType="cluster" subjectId={c.id} existing={packets ?? []} />
          <AskCase subjectType="cluster" subjectId={c.id} />
        </div>
        <div className="card p-5 overflow-x-auto"><h2 className="serif text-[24px] mb-3">Providers in this network</h2>
          <table className="table"><thead><tr><th>type</th><th>organisation</th><th>where</th><th>incorporated</th><th>on a list</th><th>Medicaid 2024</th></tr></thead>
            <tbody>{members?.map(m => { const labels = ((typeof m.labels === "string" ? JSON.parse(m.labels) : m.labels) ?? []).map((l: string) => l === "OIG_LEIE" ? "OIG exclusion" : l === "MEDICARE_REVOKED" ? "Medicare revocation" : l === "MEDICAID_TERM" ? "state termination" : l === "NPI_DEACTIVATED" ? "NPI deactivated" : l.replace(/_/g, " ").toLowerCase()); return <tr key={m.enrollment_id}><td>{m.ptype === "HHA" ? "home health" : m.ptype === "SNF" ? "nursing facility" : "hospice"}</td><td><Link href={`/app/providers/${m.npi}`} className="link">{m.org_name}</Link><div className="text-[11px] text-[var(--ink-3)]">{m.npi}</div></td><td>{m.city}, {m.state}</td><td>{m.inc_date ?? ""}</td><td className="text-[11px] font-semibold">{labels.join(", ")}</td><td>{money(m.medicaid_2024)}</td></tr>; })}</tbody></table>
        </div>
      </div>
    </div>
  );
}

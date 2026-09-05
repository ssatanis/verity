import Link from "next/link";
import { publicClient, money } from "@/lib/supabase";
import { ForceGraph } from "@/components/app/ForceGraph";
import { PacketPanel } from "@/components/app/PacketPanel";
export const revalidate = 60;
export default async function Cluster({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; const sb = publicClient();
  const [{ data: c }, { data: members }, { data: packets }] = await Promise.all([
    sb.from("clusters").select("*").eq("id", id).maybeSingle(),
    sb.from("cluster_members").select("*").eq("cluster_id", id).order("medicaid_2024", { ascending: false }),
    sb.from("packets").select("id,status,packet,created_at,model").eq("subject_id", id).order("created_at", { ascending: false }).limit(1),
  ]);
  if (!c) return <div>Not found</div>;
  const f = (typeof c.features === "string" ? JSON.parse(c.features) : c.features) ?? {};
  const graph = typeof c.graph === "string" ? JSON.parse(c.graph) : c.graph;
  const feats: [string, any][] = [["providers", c.n_providers], ["incorporated within 90 days", f.burst_90], ["formed since 2021", f.n_new], ["most at one building", f.addr_share], ["most in one suite", f.unit_share], ["owners with 3+ members", f.owner_multi], ["largest owner degree", f.max_owner_degree], ["share a phone", f.phone_share], ["share an official", f.ao_share], ["exclusion links", f.excluded_link], ["revoked members", f.revoked_nbr], ["Medicaid terminations", f.medicaid_term_nbr], ["state exclusions", f.state_excl], ["providers per 10k FFS (county)", f.sat_per_10k != null ? Number(f.sat_per_10k).toFixed(1) : null], ["saturation robust z", f.sat_z != null ? Number(f.sat_z).toFixed(2) : null], ["structure score", Number(c.structure_score).toFixed(2)], ["label score", Number(c.label_score).toFixed(2)], ["context score", Number(c.context_score).toFixed(2)]];
  return (
    <div>
      <Link href="/app/clusters" className="text-[12px] text-[var(--ink-3)]">Communities</Link>
      <div className="flex items-start justify-between gap-6 mt-1 mb-5">
        <div><h1 className="serif text-[36px] leading-none">{c.id} <span className="text-[var(--ink-3)]">{c.city}</span></h1><p className="text-[13px] text-[var(--ink-2)] mt-3 max-w-3xl leading-6">{c.summary}</p></div>
        <div className="kpi min-w-[180px] text-right"><div className="text-[11px] text-[var(--ink-3)]">risk score · rank {c.rank}</div><div className="serif text-[34px]">{Number(c.score).toFixed(2)}</div><div className="text-[11px] text-[var(--ink-3)]">{money(c.dollars_at_risk)} Medicaid 2024 · {money(c.dollars_medicare)} Medicare 2023</div></div>
      </div>
      <div className="card bg-white p-2 mb-6"><ForceGraph graph={graph} /></div>
      <div className="grid md:grid-cols-[1fr_1.4fr] gap-6">
        <div>
          <div className="card bg-white p-5 mb-6"><h2 className="serif text-[22px] mb-3">Features</h2>
            <table className="table w-full"><tbody>{feats.filter(([, v]) => v != null).map(([k, v]) => <tr key={k}><td className="text-[var(--ink-3)]">{k}</td><td className="text-right">{String(v)}</td></tr>)}</tbody></table>
            {f.burst_90_span && <div className="text-[11px] text-[var(--ink-3)] mt-2">Burst window {f.burst_90_span[0]} to {f.burst_90_span[1]}</div>}
          </div>
          <PacketPanel subjectType="cluster" subjectId={c.id} existing={packets ?? []} />
        </div>
        <div className="card bg-white p-5 overflow-x-auto"><h2 className="serif text-[22px] mb-3">Members</h2>
          <table className="table w-full"><thead><tr><th>type</th><th>provider</th><th>where</th><th>incorporated</th><th>lists</th><th>Medicaid 2024</th></tr></thead>
            <tbody>{members?.map(m => <tr key={m.enrollment_id}><td>{m.ptype}</td><td><Link href={`/app/providers/${m.npi}`} className="link-underline">{m.org_name}</Link><div className="text-[11px] text-[var(--ink-3)]">{m.npi}</div></td><td>{m.city}, {m.state}</td><td>{m.inc_date ?? ""}</td><td className="text-[var(--red)] text-[11px]">{(typeof m.labels === "string" ? JSON.parse(m.labels) : m.labels)?.join(", ")}</td><td>{money(m.medicaid_2024)}</td></tr>)}</tbody></table>
        </div>
      </div>
    </div>
  );
}

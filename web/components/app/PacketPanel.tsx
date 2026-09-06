"use client";
import { useState } from "react";
import { money, ordinal, moneyExact } from "@/lib/labels";
export function PacketPanel({ subjectType, subjectId, existing }: { subjectType: "cluster" | "provider"; subjectId: string; existing?: any[] }) {
  const [packet, setPacket] = useState<any>(existing?.[0] ?? null);
  const [busy, setBusy] = useState(false); const [result, setResult] = useState<any>(null); const [note, setNote] = useState("");
  async function generate() {
    setBusy(true); setResult(null);
    const r = await fetch("/api/packets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_type: subjectType, subject_id: subjectId }) });
    setPacket(await r.json()); setBusy(false);
  }
  async function decide(decision: string) {
    setBusy(true);
    const r = await fetch("/api/reviews", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ packet_id: packet.id, decision, notes: note }) });
    setResult(await r.json()); setPacket({ ...packet, status: decision === "accept" ? "accepted" : decision === "reject" ? "rejected" : "needs_info" }); setBusy(false);
  }
  const p = packet?.packet ?? packet;
  const drafted = p?.model ? (String(p.model).startsWith("claude") ? "Drafted by the investigator agent from the evidence rows" : String(p.model).startsWith("deterministic") ? "Assembled from the evidence rows without a model" : String(p.model)) : "";
  const status: Record<string, string> = { draft: "Awaiting review", accepted: "Accepted by reviewer", rejected: "Rejected by reviewer", needs_info: "Records requested" };
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="serif text-[24px]">Referral packet</h2>
        <div className="flex gap-2">{packet?.id && <a href={`/api/packets/${packet.id}/pdf`} target="_blank" className="btn btn-ghost" style={{ padding: "8px 14px" }}>Download PDF</a>}<button onClick={generate} disabled={busy} className="btn" style={{ padding: "8px 14px" }}>{busy ? "Working" : packet ? "Redraft" : "Draft packet"}</button></div>
      </div>
      {!packet && <p className="text-[13px] text-[var(--ink-2)] mt-2 leading-6">The packet is a draft for a reviewer. It reads every public record behind this case, states what the records show with a citation for each finding, names the regulation each finding relates to, and lists the ordinary explanations to rule out first. It never asserts intent.</p>}
      {p && (
        <div className="mt-4 text-[13.5px]">
          <div className="flex flex-wrap items-center gap-2 text-[11px]"><span className="tag">{drafted}</span><span className={`tag ${packet.status === "accepted" ? "tag-accent" : packet.status === "rejected" ? "tag-danger" : ""}`}>{status[packet.status ?? "draft"] ?? packet.status}</span>{p.findings_dropped ? <span className="tag tag-danger">{p.findings_dropped} unsupported statement(s) removed</span> : null}</div>
          <h3 className="serif text-[22px] mt-3">{p.title}</h3>
          <p className="mt-2 leading-6">{p.summary}</p>
          <div className="mt-4"><div className="eyebrow mb-1">Description</div><p className="leading-6">{p.plain_english}</p></div>
          <div className="mt-4"><div className="eyebrow mb-2">What the records show</div>
            <ol className="space-y-2">{p.findings?.map((f: any, i: number) => <li key={i} className="flex gap-4"><span className="serif text-[17px] shrink-0 w-7" style={{ color: "var(--blue)" }}>{String(i + 1).padStart(2, "0")}</span><span>{f.text} <span className="text-[var(--ink-3)] text-[11px]">records {f.evidence_ids?.map((n: number) => n + 1).join(", ")}</span></span></li>)}</ol></div>
          <div className="mt-4"><div className="eyebrow mb-1">Regulations this relates to</div>{p.grounds?.map((g: any) => <div key={g.cfr} className="py-1.5 rule"><span className="font-semibold">42 CFR {g.cfr}</span> <span className="text-[var(--ink-2)]">{String(g.text).replace(/^42 CFR [^:]+:\s*/, "")}</span></div>)}</div>
          <div className="mt-4"><div className="eyebrow mb-1">Recommended next step</div><p className="leading-6">{p.recommendation}</p></div>
          {p.procedures?.length ? <div className="mt-4"><div className="eyebrow mb-2">Procedures behind the dollars</div>
            <div className="overflow-x-auto"><table className="table"><thead><tr><th>program</th><th>code</th><th>what it is</th><th>paid</th><th>share</th><th>comparison</th></tr></thead>
              <tbody>{p.procedures.map((c: any, i: number) => <tr key={i}><td className="text-[11px]">{c.program}</td><td className="mono">{c.code}</td><td className="text-[12px] max-w-[260px]">{c.description || ""}{c.high_vector ? <span className="tag tag-danger ml-2">history of abuse</span> : null}</td><td>{money(c.paid)}</td><td><div className="flex items-center gap-2"><div className="w-[60px] h-[6px] bg-[var(--paper-2)]"><div className="h-[6px]" style={{ width: `${Math.max(2, Number(c.share) * 100)}%`, background: "var(--blue)" }} /></div><span className="text-[11px]">{Math.round(Number(c.share) * 100)}%</span></div></td><td className="text-[11.5px] text-[var(--ink-2)]">{c.percentile != null ? `${ordinal(Number(c.percentile) * 100)} percentile of providers on this code (${moneyExact(c.per_patient_month)} per patient-month, typical ${moneyExact(c.typical)})` : c.charge_ratio != null ? `charge to allowed ${Number(c.charge_ratio).toFixed(1)}x${c.peer_ratio != null ? `, usual ${Number(c.peer_ratio).toFixed(1)}x` : ""}` : ""}</td></tr>)}</tbody></table></div></div> : null}
          {p.caveats?.length ? <div className="mt-4"><div className="eyebrow mb-1">Rule out first</div><ul className="space-y-1.5 text-[13px] text-[var(--ink-2)]">{p.caveats.map((c: string, i: number) => <li key={i} className="flex gap-3"><span aria-hidden className="shrink-0 mt-[7px]" style={{ width: 5, height: 5, background: "var(--blue)" }} /><span>{c}</span></li>)}</ul></div> : null}
          <details className="mt-4"><summary className="eyebrow cursor-pointer">Sources, {p.evidence?.length} public records</summary>
            <ol className="mt-2 space-y-1 text-[12px]">{p.evidence?.map((e: any) => <li key={e.id}><span className="text-[var(--ink-3)]">{e.id + 1}. {e.source}:</span> {e.statement}</li>)}</ol></details>
          <div className="mt-5 pt-4" style={{ borderTop: "1px solid var(--blue)" }}>
            <div className="eyebrow mb-2">Your decision</div>
            <input value={note} onChange={e => setNote(e.target.value)} placeholder="Why, in a sentence. A rejection reason is used to learn which kind of evidence was wrong." className="w-full mb-2" />
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => decide("accept")} disabled={busy || !packet.id} className="btn" style={{ padding: "8px 14px" }}>Accept</button>
              <button onClick={() => decide("reject")} disabled={busy || !packet.id} className="btn btn-ghost" style={{ padding: "8px 14px" }}>Reject</button>
              <button onClick={() => decide("needs_info")} disabled={busy || !packet.id} className="btn btn-ghost" style={{ padding: "8px 14px" }}>Request records</button>
            </div>
            {result && <div className="text-[12px] text-[var(--ink-2)] mt-3 leading-5">{result.note_family ? <>Your reason was filed under <b>{result.note_family.family}</b> evidence: {result.note_family.reason} </> : null}{result.message}</div>}
          </div>
        </div>
      )}
    </div>
  );
}

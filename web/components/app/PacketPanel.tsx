"use client";
import { useState } from "react";

export function PacketPanel({ subjectType, subjectId, existing }: { subjectType: "cluster" | "provider"; subjectId: string; existing?: any[] }) {
  const [packet, setPacket] = useState<any>(existing?.[0] ?? null);
  const [busy, setBusy] = useState(false); const [weights, setWeights] = useState<any>(null); const [note, setNote] = useState("");
  async function generate() {
    setBusy(true);
    const r = await fetch("/api/packets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_type: subjectType, subject_id: subjectId }) });
    setPacket(await r.json()); setBusy(false);
  }
  async function decide(decision: string) {
    setBusy(true);
    const r = await fetch("/api/reviews", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ packet_id: packet.id, decision, notes: note }) });
    const j = await r.json(); setWeights(j); setPacket({ ...packet, status: decision }); setBusy(false);
  }
  const p = packet?.packet ?? packet;
  return (
    <div className="card bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="serif text-[22px]">Referral packet</h2>
        <button onClick={generate} disabled={busy} className="btn-dark text-[12px]">{busy ? "Working" : packet ? "Regenerate" : "Generate packet"}</button>
      </div>
      {!packet && <p className="text-[12px] text-[var(--ink-3)] mt-2">The investigator agent pulls every evidence row, drafts a CMS-style referral with 42 CFR grounds, and writes a plain-English explanation. Every sentence cites the row it came from.</p>}
      {p && (
        <div className="mt-4 text-[13px]">
          <div className="flex items-center gap-2 text-[11px] text-[var(--ink-3)]"><span className="tag">{p.model}</span><span className="tag">{packet.status ?? "draft"}</span>{packet.id && <span>{packet.id}</span>}</div>
          <h3 className="font-medium mt-3">{p.title}</h3>
          <p className="mt-2 leading-6">{p.summary}</p>
          <div className="mt-3"><div className="text-[11px] text-[var(--ink-3)] mb-1">Plain English</div><p className="leading-6">{p.plain_english}</p></div>
          <div className="mt-3"><div className="text-[11px] text-[var(--ink-3)] mb-1">Findings (each cites evidence rows)</div>
            <ol className="list-decimal pl-5 space-y-1">{p.findings?.map((f: any, i: number) => <li key={i}>{f.text} <span className="text-[var(--ink-3)]">[{f.evidence_ids?.join(", ")}]</span></li>)}</ol></div>
          <div className="mt-3"><div className="text-[11px] text-[var(--ink-3)] mb-1">Regulatory grounds</div>{p.grounds?.map((g: any) => <div key={g.cfr}><span className="font-medium">42 CFR {g.cfr}</span> <span className="text-[var(--ink-2)]">{g.text}</span></div>)}</div>
          <div className="mt-3"><div className="text-[11px] text-[var(--ink-3)] mb-1">Recommendation</div><p className="leading-6">{p.recommendation}</p></div>
          <details className="mt-3"><summary className="text-[11px] text-[var(--ink-3)] cursor-pointer">Evidence trail ({p.evidence?.length} rows)</summary>
            <ol className="mt-2 space-y-1 text-[11.5px]">{p.evidence?.map((e: any) => <li key={e.id}><span className="text-[var(--ink-3)]">[{e.id}] {e.source}:</span> {e.statement}</li>)}</ol></details>
          <div className="mt-5 border-t border-[var(--line)] pt-4">
            <div className="text-[11px] text-[var(--ink-3)] mb-2">Reviewer decision (feeds the score)</div>
            <input value={note} onChange={e => setNote(e.target.value)} placeholder="Notes for the record" className="w-full border border-[var(--line)] rounded-md px-3 py-2 text-[12px] mb-2" />
            <div className="flex gap-2">
              <button onClick={() => decide("accept")} disabled={busy || !packet.id} className="btn-dark text-[12px] bg-[var(--green)]">Accept</button>
              <button onClick={() => decide("reject")} disabled={busy || !packet.id} className="btn-dark text-[12px] bg-[var(--red)]">Reject</button>
              <button onClick={() => decide("needs_info")} disabled={busy || !packet.id} className="btn-dark text-[12px] bg-[var(--ink-3)]">Needs info</button>
            </div>
            {weights && <div className="text-[11px] text-[var(--ink-3)] mt-3">Score weights updated from {weights.n_reviews} reviews: {JSON.stringify(weights.weights)}</div>}
          </div>
        </div>
      )}
    </div>
  );
}

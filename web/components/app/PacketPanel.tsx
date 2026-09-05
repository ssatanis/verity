"use client";
import { useState } from "react";
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
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="serif text-[24px]">Referral candidate packet</h2>
        <div className="flex gap-2">{packet?.id && <a href={`/api/packets/${packet.id}/pdf`} target="_blank" className="btn btn-ghost" style={{ padding: "8px 14px" }}>PDF</a>}<button onClick={generate} disabled={busy} className="btn" style={{ padding: "8px 14px" }}>{busy ? "Working" : packet ? "Regenerate" : "Draft packet"}</button></div>
      </div>
      {!packet && <p className="text-[12.5px] text-[var(--ink-3)] mt-2 leading-5">The investigator agent reads every evidence row for this subject, drafts findings that each cite their rows, maps the evidence types to 42 CFR grounds, and lists the caveats a reviewer must rule out. Nothing in the packet asserts intent.</p>}
      {p && (
        <div className="mt-4 text-[13px]">
          <div className="flex flex-wrap items-center gap-2 text-[11px]"><span className="tag">{p.model}</span><span className={`tag ${packet.status === "accepted" ? "tag-accent" : packet.status === "rejected" ? "tag-danger" : ""}`}>{packet.status ?? "draft"}</span>{p.findings_dropped ? <span className="tag tag-danger">{p.findings_dropped} unsupported finding(s) removed</span> : null}{packet.id && <span className="mono text-[var(--ink-3)]">{String(packet.id).slice(0, 8)}</span>}</div>
          <h3 className="serif text-[20px] mt-3">{p.title}</h3>
          <p className="mt-2 leading-6">{p.summary}</p>
          <div className="mt-3"><div className="eyebrow mb-1">Plain language</div><p className="leading-6">{p.plain_english}</p></div>
          <div className="mt-3"><div className="eyebrow mb-1">Findings, each citing evidence rows</div>
            <ol className="space-y-2">{p.findings?.map((f: any, i: number) => <li key={i} className="flex gap-3"><span className="serif text-[16px] shrink-0" style={{ color: "var(--accent)" }}>{String(i + 1).padStart(2, "0")}</span><span>{f.text} <span className="text-[var(--ink-3)] text-[11px]">[{f.evidence_ids?.join(", ")}]</span></span></li>)}</ol></div>
          <div className="mt-3"><div className="eyebrow mb-1">Regulatory grounds</div>{p.grounds?.map((g: any) => <div key={g.cfr} className="py-1 rule"><span className="font-medium">42 CFR {g.cfr}</span> <span className="text-[var(--ink-2)]">{g.text}</span></div>)}</div>
          <div className="mt-3"><div className="eyebrow mb-1">Recommendation</div><p className="leading-6">{p.recommendation}</p></div>
          {p.caveats?.length ? <div className="mt-3"><div className="eyebrow mb-1">Rule out first</div><ul className="space-y-1 text-[12.5px] text-[var(--ink-2)]">{p.caveats.map((c: string, i: number) => <li key={i}>{c}</li>)}</ul></div> : null}
          <details className="mt-3"><summary className="eyebrow cursor-pointer">Evidence trail, {p.evidence?.length} rows</summary>
            <ol className="mt-2 space-y-1 text-[11.5px]">{p.evidence?.map((e: any) => <li key={e.id}><span className="text-[var(--ink-3)]">[{e.id}] {e.source}:</span> {e.statement}</li>)}</ol></details>
          <div className="mt-5 pt-4" style={{ borderTop: "1px solid var(--ink)" }}>
            <div className="eyebrow mb-2">Reviewer decision</div>
            <input value={note} onChange={e => setNote(e.target.value)} placeholder="Why, in a sentence. A rejection reason is classified to the evidence family that was wrong." className="w-full mb-2" />
            <div className="flex gap-2">
              <button onClick={() => decide("accept")} disabled={busy || !packet.id} className="btn btn-accent" style={{ padding: "8px 14px" }}>Accept</button>
              <button onClick={() => decide("reject")} disabled={busy || !packet.id} className="btn" style={{ padding: "8px 14px", background: "var(--danger)", borderColor: "var(--danger)" }}>Reject</button>
              <button onClick={() => decide("needs_info")} disabled={busy || !packet.id} className="btn btn-ghost" style={{ padding: "8px 14px" }}>Needs records</button>
            </div>
            {result && <div className="text-[11.5px] text-[var(--ink-2)] mt-3 leading-5">{result.note_family ? <>Note classified as <b>{result.note_family.family}</b>: {result.note_family.reason} </> : null}{result.message} Current weights {JSON.stringify(result.weights)}.</div>}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
export function AskCase({ subjectType, subjectId }: { subjectType: "cluster" | "provider"; subjectId: string }) {
  const [q, setQ] = useState(""); const [busy, setBusy] = useState(false);
  const [turns, setTurns] = useState<{ role: "user" | "assistant"; content: string; tools?: string[] }[]>([]);
  const suggestions = subjectType === "cluster"
    ? ["Which owners connect the most providers?", "Which providers are on a public list, and when?", "What happened in the incorporation window?", "Summarize the strongest evidence in five sentences."]
    : ["What is the timeline of the list action and the payments after it?", "Which organizations billed under this NPI in the flagged months?", "What must a reviewer rule out before acting?", "Summarize this case in five sentences."];
  async function ask(text: string) {
    if (!text.trim() || busy) return; setBusy(true); setQ("");
    const history = turns.map(t => ({ role: t.role, content: t.content }));
    setTurns(t => [...t, { role: "user", content: text }]);
    try {
      const r = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_type: subjectType, subject_id: subjectId, question: text, history }), signal: AbortSignal.timeout(160000) });
      const ct = r.headers.get("content-type") ?? ""; const j = ct.includes("json") ? await r.json() : { error: `The assistant did not answer (status ${r.status}).` };
      setTurns(t => [...t, { role: "assistant", content: j.answer ?? `Could not answer: ${j.error ?? "unknown error"}`, tools: j.tools_used }]);
    } catch (e: any) {
      setTurns(t => [...t, { role: "assistant", content: e?.name === "TimeoutError" ? "The assistant took too long. Try a narrower question, for example about one provider or one date." : `Could not reach the assistant: ${e?.message ?? "network error"}` }]);
    } finally { setBusy(false); }
  }
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3 flex-wrap"><h2 className="serif text-[24px]">Ask this case</h2><span className="text-[11px] text-[var(--ink-3)]">Answers come only from the evidence tables, and every sentence cites the record it used.</span></div>
      {!turns.length && <div className="flex flex-wrap gap-2 mt-3">{suggestions.map(s => <button key={s} onClick={() => ask(s)} className="tag hover:bg-[var(--paper-2)] text-left">{s}</button>)}</div>}
      <div className="mt-3 space-y-4 max-h-[480px] overflow-y-auto pr-1">
        {turns.map((t, i) => t.role === "user"
          ? <div key={i} className="serif text-[18px]" style={{ color: "var(--blue)" }}>{t.content}</div>
          : <div key={i} className="prose-methods text-[13.5px] leading-6 pl-3" style={{ borderLeft: "2px solid var(--blue)" }}><ReactMarkdown>{t.content}</ReactMarkdown>{t.tools?.length ? <div className="text-[11px] text-[var(--ink-3)] mt-1">Consulted: {t.tools.map(x => x.replace(/^get_/, "").replace(/_/g, " ")).join(", ")}</div> : null}</div>)}
        {busy && <div className="text-[12px] text-[var(--ink-3)] flex items-center gap-2"><span className="inline-block w-2 h-2" style={{ background: "var(--blue)", animation: "pulse 1s infinite" }} />Reading the evidence tables</div>}
      </div>
      <form onSubmit={e => { e.preventDefault(); ask(q); }} className="flex gap-2 mt-4"><input value={q} onChange={e => setQ(e.target.value)} placeholder="Ask about owners, dates, payments, lists" className="flex-1" disabled={busy} /><button className="btn" disabled={busy}>Ask</button>{turns.length > 0 && <button type="button" onClick={() => setTurns([])} className="btn btn-ghost" disabled={busy}>Clear</button>}</form>
    </div>
  );
}

"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
export function AskCase({ subjectType, subjectId }: { subjectType: "cluster" | "provider"; subjectId: string }) {
  const [q, setQ] = useState(""); const [busy, setBusy] = useState(false);
  const [turns, setTurns] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const suggestions = subjectType === "cluster" ? ["Which owners connect the most members?", "Which members are on a list, and when?", "What happened in the incorporation burst window?"] : ["What is the timeline of the action and the payments after it?", "Which organisations billed under this NPI in the flagged months?", "What must a reviewer rule out before acting?"];
  async function ask(text: string) {
    if (!text.trim() || busy) return; setBusy(true); setQ("");
    const history = turns.map(t => ({ role: t.role, content: t.content }));
    setTurns(t => [...t, { role: "user", content: text }]);
    const r = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject_type: subjectType, subject_id: subjectId, question: text, history }) });
    const j = await r.json(); setTurns(t => [...t, { role: "assistant", content: j.answer ?? `Could not answer: ${j.error ?? "unknown error"}` }]); setBusy(false);
  }
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between"><h2 className="serif text-[24px]">Ask this case</h2><span className="text-[11px] text-[var(--ink-3)]">Answers only from evidence tools; every sentence cites a row</span></div>
      {!turns.length && <div className="flex flex-wrap gap-2 mt-3">{suggestions.map(s => <button key={s} onClick={() => ask(s)} className="tag hover:bg-[var(--paper-2)]">{s}</button>)}</div>}
      <div className="mt-3 space-y-3 max-h-[420px] overflow-y-auto">{turns.map((t, i) => <div key={i} className={`text-[13px] leading-6 ${t.role === "user" ? "serif text-[17px]" : "prose-methods"}`} style={t.role === "user" ? { color: "var(--accent)" } : {}}>{t.role === "user" ? t.content : <ReactMarkdown>{t.content}</ReactMarkdown>}</div>)}{busy && <div className="text-[12px] text-[var(--ink-3)]">Reading the evidence tables</div>}</div>
      <form onSubmit={e => { e.preventDefault(); ask(q); }} className="flex gap-2 mt-4"><input value={q} onChange={e => setQ(e.target.value)} placeholder="Ask about owners, dates, payments, lists" className="flex-1" /><button className="btn" disabled={busy}>Ask</button></form>
    </div>
  );
}

import { NextResponse } from "next/server";
import { z } from "zod";
import { zodOutputFormat } from "@anthropic-ai/sdk/helpers/zod";
import { serviceClient } from "@/lib/supabase";
import { evidenceLines, deterministicPacket } from "@/lib/packet";
import { claude, claudeReady, cleanText, MODEL } from "@/lib/claude";

const Draft = z.object({
  summary: z.string(), plain_english: z.string(),
  findings: z.array(z.object({ text: z.string(), evidence_ids: z.array(z.number().int()) })),
  recommendation: z.string(), caveats: z.array(z.string()),
});
const SYSTEM = `You draft referral candidate packets for health plan special investigations units and state Medicaid program integrity units.
Rules: every finding must be supported verbatim by the evidence lines and cite their ids; never add a fact that is not in the evidence; describe records, dates and amounts and never assert fraud, intent or guilt; use only the regulatory grounds provided, by citation; plain English, short sentences; no em dashes, no en dashes, no underscores and no code-like identifiers (write list names and labels in words); the plain_english field is a specific three-to-five sentence description of this subject drawn from the evidence, never a generic paragraph; include caveats naming the legitimate explanations a reviewer must rule out.`;

export async function POST(req: Request) {
  const { subject_type, subject_id, created_by = "console" } = await req.json();
  if (!["cluster", "provider"].includes(subject_type) || !subject_id) return NextResponse.json({ error: "bad request" }, { status: 400 });
  const sb = serviceClient();
  const { lines, types } = await evidenceLines(sb, subject_type, subject_id);
  if (!lines.length) return NextResponse.json({ error: "not found" }, { status: 404 });
  const name = subject_type === "provider" ? (await sb.from("providers").select("name").eq("npi", subject_id).maybeSingle()).data?.name : undefined;
  let packet = deterministicPacket(subject_type, subject_id, lines, types, name);
  if (claudeReady()) {
    try {
      const r = await claude().messages.parse({ model: MODEL, max_tokens: 8000, system: SYSTEM, output_config: { effort: "high" },
        messages: [{ role: "user", content: JSON.stringify({ subject: packet.title, evidence: packet.evidence, regulatory_grounds: packet.grounds, evidence_types: types }) }],
        output_format: zodOutputFormat(Draft) });
      const d = r.parsed_output as z.infer<typeof Draft> | null; const n = lines.length;
      if (d) {
        const ok = d.findings.filter(f => f.evidence_ids.length && f.evidence_ids.every(i => i >= 0 && i < n));
        packet = cleanText({ ...packet, model: MODEL, summary: d.summary || packet.summary, plain_english: d.plain_english || packet.plain_english, findings: ok.length ? ok : packet.findings, recommendation: d.recommendation || packet.recommendation, caveats: d.caveats?.length ? d.caveats : packet.caveats, findings_dropped: d.findings.length - ok.length });
      }
    } catch (e: any) { packet = { ...packet, model: `deterministic (model unavailable: ${String(e?.message ?? e).slice(0, 80)})` }; }
  }
  const { data, error } = await sb.from("packets").insert({ subject_type, subject_id, status: "draft", packet, created_by, title: packet.title, cluster_id: subject_type === "cluster" ? subject_id : null, npi: subject_type === "provider" ? subject_id : null, model: packet.model }).select("id").single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  try { await sb.storage.from("verity-packets").upload(`${subject_type}/${subject_id}/${data.id}.json`, JSON.stringify(packet), { contentType: "application/json", upsert: true }); } catch {}
  return NextResponse.json({ id: data.id, status: "draft", packet });
}

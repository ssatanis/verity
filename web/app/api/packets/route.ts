import { NextResponse } from "next/server";
import { z } from "zod";
import { zodOutputFormat } from "@anthropic-ai/sdk/helpers/zod";
import { serviceClient } from "@/lib/supabase";
import { evidenceLines, deterministicPacket } from "@/lib/packet";
import { claude, claudeReady, cleanText, MODEL, STYLE } from "@/lib/claude";
import { readJson, subjectOk, str } from "@/lib/validate";

const Draft = z.object({
  summary: z.string(), plain_english: z.string(),
  findings: z.array(z.object({ text: z.string(), evidence_ids: z.array(z.number().int()) })),
  recommendation: z.string(), caveats: z.array(z.string()),
});
const SYSTEM = `You draft referral candidate packets for health plan special investigations units and state Medicaid program integrity units.

What the packet must be true to:
- Every finding is supported verbatim by the evidence lines and cites their ids. Never add a fact that is not in the evidence.
- Describe records, dates and amounts. Never assert fraud, intent or guilt.
- Use only the regulatory grounds provided, by citation.
- Include caveats naming the legitimate explanations a reviewer must rule out.

How each field reads:
- summary: three to five sentences. The first says what the record is and when. The rest add one fact each. It is a paragraph of separate sentences, never one long sentence.
- plain_english: three to five sentences describing this specific subject, drawn from the evidence. Never a generic paragraph, and never a restatement of the summary.
- findings: one sentence each, or two short ones. No sentence carries more than one figure.
- recommendation: two to four sentences saying what to do next and under which rule.
- caveats: one sentence each.

${STYLE}`;

export async function POST(req: Request) {
  const body = await readJson(req); if (!body) return NextResponse.json({ error: "bad request" }, { status: 400 });
  const { subject_type, subject_id } = body; const created_by = str(body.created_by, 80).trim() || "console";
  if (!subjectOk(subject_type, subject_id)) return NextResponse.json({ error: "bad request" }, { status: 400 });
  const sb = serviceClient();
  const { lines, types, procedures } = await evidenceLines(sb, subject_type, subject_id);
  if (!lines.length) return NextResponse.json({ error: "not found" }, { status: 404 });
  const name = subject_type === "provider" ? (await sb.from("providers").select("name").eq("npi", subject_id).maybeSingle()).data?.name : undefined;
  let packet = deterministicPacket(subject_type, subject_id, lines, types, name, procedures);
  if (claudeReady()) {
    try {
      // structured output goes through output_config.format (the top-level output_format field is deprecated by the API)
      const r = await claude().messages.parse({ model: MODEL, max_tokens: 8000, system: SYSTEM, output_config: { effort: "high", format: zodOutputFormat(Draft) } as any,
        messages: [{ role: "user", content: JSON.stringify({ subject: packet.title, evidence: packet.evidence, regulatory_grounds: packet.grounds, evidence_types: types }) }] });
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

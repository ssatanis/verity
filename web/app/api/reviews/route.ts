import { NextResponse } from "next/server";
import { z } from "zod";
import { zodOutputFormat } from "@anthropic-ai/sdk/helpers/zod";
import { serviceClient } from "@/lib/supabase";
import { claude, claudeReady, cleanText } from "@/lib/claude";

// Families per detector. A rejection note is classified to the family that was wrong, so only that family's weight moves.
const FAMILIES: Record<string, string[]> = { D1: ["structure", "label", "context"], D2: ["volume", "rate", "convention"], D3: ["identity", "timing", "list"] };
const Cls = z.object({ family: z.string(), reason: z.string(), confidence: z.number() });
async function classify(detector: string, notes: string) {
  const fams = FAMILIES[detector] ?? []; if (!notes?.trim() || !claudeReady() || !fams.length) return null;
  const guide: Record<string, string> = {
    D1: "structure = ownership, incorporation timing, shared suites or phones were wrong or innocent; label = the exclusion, revocation or termination link was wrong; context = market saturation or county context was misleading",
    D2: "volume = the hours or patient counts were misread or the codes are not personal service; rate = the unit price assumption was wrong; convention = the rendering NPI is a supervising or umbrella NPI under state convention",
    D3: "identity = wrong person or entity (name or NPI mismatch); timing = payment months fall before the action or after a reinstatement or appeal; list = the list action was administrative or not a screening trigger",
  };
  try {
    const r = await claude().messages.parse({ model: "claude-haiku-4-5", max_tokens: 400, output_format: zodOutputFormat(Cls),
      system: `Classify a reviewer's rejection note for detector ${detector} into exactly one evidence family from ${JSON.stringify(fams)} or "none" when the note gives no reason. Guide: ${guide[detector]}. Return the family, a one-sentence reason without em dashes, and a confidence from 0 to 1.`,
      messages: [{ role: "user", content: notes.slice(0, 2000) }] });
    const p = r.parsed_output as z.infer<typeof Cls> | null; if (!p || !fams.includes(p.family)) return null; return cleanText(p);
  } catch { return null; }
}
export async function POST(req: Request) {
  const { packet_id, decision, reviewer = "console", notes = "" } = await req.json();
  if (!["accept", "reject", "needs_info"].includes(decision)) return NextResponse.json({ error: "bad decision" }, { status: 400 });
  const sb = serviceClient();
  const { data: p } = await sb.from("packets").select("subject_type,subject_id").eq("id", packet_id).maybeSingle();
  if (!p) return NextResponse.json({ error: "not found" }, { status: 404 });
  let detector = "D1"; let score: number | null = null;
  if (p.subject_type === "cluster") score = (await sb.from("clusters").select("score").eq("id", p.subject_id).maybeSingle()).data?.score ?? null;
  else { const r = (await sb.from("provider_risk").select("tier,score,detectors").eq("npi", p.subject_id).maybeSingle()).data; detector = (r?.detectors?.[0] as string) ?? "D3"; score = r?.score ?? null; }
  const cls = decision === "reject" ? await classify(detector, notes) : null;
  await sb.from("reviews").insert({ packet_id, subject_type: p.subject_type, subject_id: p.subject_id, decision, reviewer, notes, detector, score_at_review: score, notes_family: cls?.family ?? null });
  await sb.from("packets").update({ status: decision === "accept" ? "accepted" : decision === "reject" ? "rejected" : "needs_info" }).eq("id", packet_id);
  // Beta-binomial re-weighting per family. Accept credits every family present in the case; a classified rejection debits only its family; an unclassified rejection debits every family present.
  const { data: rows } = detector === "D1" ? await sb.from("reviews").select("decision, notes_family, clusters!inner(features)").eq("detector", "D1") : await sb.from("reviews").select("decision, notes_family").eq("detector", detector);
  const prior = 4; const fams = FAMILIES[detector] ?? ["evidence"]; const weights: Record<string, number> = {}; const counts: Record<string, [number, number]> = {};
  for (const fam of fams) {
    const present = (r: any) => detector !== "D1" || !!J(r.clusters?.features)?.[`${fam}_family`];
    let a = 0, b = 0;
    for (const r of rows ?? []) { if (!present(r)) continue; if (r.decision === "accept") a++; else if (r.decision === "reject" && (!r.notes_family || r.notes_family === fam)) b++; }
    counts[fam] = [a, b]; weights[fam] = Math.round(1000 * 2 * (a + prior / 2) / (a + b + prior)) / 1000;
  }
  const n = rows?.length ?? 0;
  await sb.from("score_weights").upsert({ detector, weights, n_reviews: n, updated_at: new Date().toISOString() });
  return NextResponse.json({ detector, weights, counts, n_reviews: n, note_family: cls, informational: n < 200, message: n < 200 ? `Weights move with each decision but stay informational until a few hundred reviews per detector; ${n} recorded so far.` : "Weights are applied at the next scoring run." });
}
const J = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};

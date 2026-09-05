import { NextResponse } from "next/server";
import { serviceClient } from "@/lib/supabase";
export async function POST(req: Request) {
  const { packet_id, decision, reviewer = "demo", notes } = await req.json();
  if (!["accept", "reject", "needs_info"].includes(decision)) return NextResponse.json({ error: "bad decision" }, { status: 400 });
  const sb = serviceClient();
  const { data: p } = await sb.from("packets").select("subject_type,subject_id").eq("id", packet_id).maybeSingle();
  if (!p) return NextResponse.json({ error: "not found" }, { status: 404 });
  let detector = "D1"; let score: number | null = null;
  if (p.subject_type === "cluster") score = (await sb.from("clusters").select("score").eq("id", p.subject_id).maybeSingle()).data?.score ?? null;
  else { const f = (await sb.from("flags").select("detector,score").eq("npi", p.subject_id).order("score", { ascending: false }).limit(1).maybeSingle()).data; detector = f?.detector ?? "D3"; score = f?.score ?? null; }
  await sb.from("reviews").insert({ packet_id, subject_type: p.subject_type, subject_id: p.subject_id, decision, reviewer, notes, detector, score_at_review: score });
  await sb.from("packets").update({ status: decision === "accept" ? "accepted" : decision === "reject" ? "rejected" : "needs_info" }).eq("id", packet_id);
  // Bayesian re-weighting of evidence families from reviewer decisions (same rule as api/main.py retrain)
  const { data: rows } = detector === "D1"
    ? await sb.from("reviews").select("decision, clusters!inner(features)").eq("detector", "D1")
    : await sb.from("reviews").select("decision").eq("detector", detector);
  const prior = 4; const fams = detector === "D1" ? ["structure", "label", "context"] : ["evidence"]; const weights: Record<string, number> = {};
  for (const fam of fams) {
    const pres = (r: any) => detector === "D1" ? !!(typeof r.clusters?.features === "string" ? JSON.parse(r.clusters.features) : r.clusters?.features)?.[`${fam}_family`] : true;
    const a = (rows ?? []).filter((r: any) => r.decision === "accept" && pres(r)).length, b = (rows ?? []).filter((r: any) => r.decision === "reject" && pres(r)).length;
    weights[fam] = Math.round(1000 * 2 * (a + prior / 2) / (a + b + prior)) / 1000;
  }
  await sb.from("score_weights").upsert({ detector, weights, n_reviews: rows?.length ?? 0, updated_at: new Date().toISOString() });
  return NextResponse.json({ detector, weights, n_reviews: rows?.length ?? 0 });
}

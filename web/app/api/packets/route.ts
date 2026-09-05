import { NextResponse } from "next/server";
import { serviceClient } from "@/lib/supabase";
import { evidenceLines, deterministicPacket, polishWithOpenAI } from "@/lib/packet";
export async function POST(req: Request) {
  const { subject_type, subject_id, created_by = "demo" } = await req.json();
  if (!["cluster", "provider"].includes(subject_type) || !subject_id) return NextResponse.json({ error: "bad request" }, { status: 400 });
  const sb = serviceClient();
  const lines = await evidenceLines(sb, subject_type, subject_id);
  if (!lines.length) return NextResponse.json({ error: "not found" }, { status: 404 });
  const name = subject_type === "provider" ? (await sb.from("providers").select("name").eq("npi", subject_id).maybeSingle()).data?.name : undefined;
  const packet = await polishWithOpenAI(deterministicPacket(subject_type, subject_id, lines, name));
  const { data, error } = await sb.from("packets").insert({ subject_type, subject_id, status: "draft", packet, created_by, title: packet.title, cluster_id: subject_type === "cluster" ? subject_id : null, npi: subject_type === "provider" ? subject_id : null, model: packet.model }).select("id").single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  try { await sb.storage.from("verity-packets").upload(`${subject_type}/${subject_id}/${data.id}.json`, JSON.stringify(packet), { contentType: "application/json", upsert: true }); } catch {}
  return NextResponse.json({ id: data.id, status: "draft", packet });
}

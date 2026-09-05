import { NextResponse } from "next/server";
import { z } from "zod";
import { betaZodTool } from "@anthropic-ai/sdk/helpers/beta/zod";
import { serviceClient } from "@/lib/supabase";
import { claude, claudeReady, cleanText, MODEL } from "@/lib/claude";

// "Ask this case": a reviewer chat that can only call evidence tools over the serving tables. Every answer must cite tool rows.
export async function POST(req: Request) {
  const { subject_type, subject_id, question, history = [] } = await req.json();
  if (!claudeReady()) return NextResponse.json({ error: "ANTHROPIC_API_KEY is not configured on the server" }, { status: 503 });
  if (!["cluster", "provider"].includes(subject_type) || !subject_id || !question) return NextResponse.json({ error: "bad request" }, { status: 400 });
  const sb = serviceClient(); const J = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
  const tools = [
    betaZodTool({ name: "get_subject", description: "The subject's summary row: community features or provider risk row.", inputSchema: z.object({}), run: async () => {
      if (subject_type === "cluster") { const { data } = await sb.from("clusters").select("id,rank,score,state,city,county,n_providers,n_hospice,n_hha,n_snf,dollars_at_risk,dollars_medicare,summary,features").eq("id", subject_id).maybeSingle(); return JSON.stringify({ ...data, features: J(data?.features) }); }
      const { data } = await sb.from("provider_risk").select("*").eq("npi", subject_id).maybeSingle(); const { data: p } = await sb.from("providers").select("*").eq("npi", subject_id).maybeSingle(); return JSON.stringify({ risk: data, provider: p }); } }),
    betaZodTool({ name: "get_members", description: "Members of the community (or the communities a provider belongs to): name, NPI, type, city, incorporation date, list labels, Medicaid 2024 dollars.", inputSchema: z.object({ limit: z.number().optional() }), run: async ({ limit }) => {
      if (subject_type === "cluster") { const { data } = await sb.from("cluster_members").select("npi,org_name,ptype,city,state,inc_date,labels,medicaid_2024,medicare_2023").eq("cluster_id", subject_id).order("medicaid_2024", { ascending: false }).limit(limit ?? 60); return JSON.stringify(data); }
      const { data } = await sb.from("cluster_members").select("cluster_id, clusters(rank,score,summary)").eq("npi", subject_id); return JSON.stringify(data); } }),
    betaZodTool({ name: "get_owners", description: "Owner and managing-employee rows from the CMS All-Owners files for the community's enrollments (or for a provider's enrollments).", inputSchema: z.object({ limit: z.number().optional() }), run: async ({ limit }) => {
      const ids = subject_type === "cluster" ? ((await sb.from("cluster_members").select("enrollment_id").eq("cluster_id", subject_id)).data ?? []).map((m: any) => m.enrollment_id) : ((await sb.from("enrollments").select("enrollment_id").eq("npi", subject_id)).data ?? []).map((m: any) => m.enrollment_id);
      if (!ids.length) return "[]"; const { data } = await sb.from("owners").select("enrollment_id,org_name,owner_type,role_text,first_name,last_name,owner_org_name,city,state,pct_ownership,association_date,flags").in("enrollment_id", ids).limit(limit ?? 120); return JSON.stringify(data); } }),
    betaZodTool({ name: "get_list_actions", description: "Medicare revocations and OIG exclusions for the subject's NPIs, with dates, grounds and re-enrollment bars.", inputSchema: z.object({}), run: async () => {
      const npis = subject_type === "cluster" ? ((await sb.from("cluster_members").select("npi").eq("cluster_id", subject_id)).data ?? []).map((m: any) => m.npi) : [subject_id];
      const [{ data: r }, { data: l }] = await Promise.all([sb.from("revoked").select("npi,org_name,first_name,last_name,state,revocation_rsn,revoked_dt,reenroll_bar_dt").in("npi", npis), sb.from("leie").select("npi,busname,firstname,lastname,state,excltype,excl_dt,rein_dt").in("npi", npis)]); return JSON.stringify({ revoked: r, leie: l }); } }),
    betaZodTool({ name: "get_payment_timeline", description: "Detector flags with dates and dollars: for D3, the action date, first and last Medicaid service month after it and dollars; for D2, each flagged month with implied hours, patients, billing organisations and codes.", inputSchema: z.object({}), run: async () => {
      const npis = subject_type === "cluster" ? ((await sb.from("cluster_members").select("npi").eq("cluster_id", subject_id)).data ?? []).map((m: any) => m.npi) : [subject_id];
      const { data } = await sb.from("flags").select("npi,detector,tier,month,metric,value,threshold,dollars,evidence").in("npi", npis).order("month").limit(200); return JSON.stringify((data ?? []).map((f: any) => ({ ...f, evidence: J(f.evidence) }))); } }),
    betaZodTool({ name: "get_saturation", description: "CMS Market Saturation rows for the community's county: providers per 10k FFS beneficiaries by service type and year.", inputSchema: z.object({}), run: async () => {
      const fips = subject_type === "cluster" ? (await sb.from("clusters").select("county_fips").eq("id", subject_id).maybeSingle()).data?.county_fips : (await sb.from("provider_risk").select("county_fips").eq("npi", subject_id).maybeSingle()).data?.county_fips;
      if (!fips) return "[]"; const { data } = await sb.from("saturation_county").select("reference_period,type_of_service,county,state,providers,ffs_beneficiaries,providers_per_10k_ffs,moratorium").eq("county_fips", String(fips).slice(-3)).eq("state", (await sb.from("county_risk").select("state").eq("county_fips", fips).maybeSingle()).data?.state ?? "").limit(40); return JSON.stringify(data); } }),
  ];
  const system = `You are the case assistant inside Verity, a provider-integrity console for health plan investigators. You may only answer from the tool results in this conversation. Every factual sentence must end with a bracketed citation naming the tool and the row, for example [get_payment_timeline: NPI 1234567893, 2022-11]. If the tools do not contain the answer, say so. Describe records, dates and amounts; never assert fraud or intent; the subject is a referral candidate. Short paragraphs, plain English, no em dashes. Subject: ${subject_type} ${subject_id}.`;
  const messages: any[] = [...history.slice(-8), { role: "user", content: question }];
  try {
    const runner = claude().beta.messages.toolRunner({ model: MODEL, max_tokens: 4000, system, tools, messages, max_iterations: 8 });
    const final = await runner.done();
    const text = cleanText(final.content.filter((b: any) => b.type === "text").map((b: any) => b.text).join("\n"));
    return NextResponse.json({ answer: text, stop_reason: final.stop_reason });
  } catch (e: any) { return NextResponse.json({ error: e?.message ?? "model error" }, { status: 500 }); }
}

import { NextResponse } from "next/server";
import React from "react";
import path from "path";
import { Document, Page, Text, View, StyleSheet, Font, renderToBuffer } from "@react-pdf/renderer";
import { serviceClient } from "@/lib/supabase";
import { UUID_RE } from "@/lib/validate";
export const runtime = "nodejs";
const F = (p: string) => path.join(process.cwd(), "node_modules/@fontsource", p);
let registered = false;
function fonts() {
  if (registered) return; registered = true;
  Font.register({ family: "Garamond", fonts: [{ src: F("eb-garamond/files/eb-garamond-latin-400-normal.woff") }, { src: F("eb-garamond/files/eb-garamond-latin-600-normal.woff"), fontWeight: 700 }] });
  Font.register({ family: "OpenSans", fonts: [{ src: F("open-sans/files/open-sans-latin-400-normal.woff") }, { src: F("open-sans/files/open-sans-latin-600-normal.woff"), fontWeight: 600 }] });
  Font.registerHyphenationCallback(w => [w]);
}
const BLUE = "#002856";
const S = StyleSheet.create({
  page: { paddingTop: 46, paddingBottom: 60, paddingHorizontal: 54, fontFamily: "OpenSans", fontSize: 9.5, color: "#000000", lineHeight: 1.5 },
  brandRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", borderBottom: `2 solid ${BLUE}`, paddingBottom: 8 },
  brand: { fontFamily: "Garamond", fontSize: 22, letterSpacing: 3, color: BLUE },
  brandSub: { fontSize: 8, color: "#666666" },
  title: { fontFamily: "Garamond", fontSize: 26, lineHeight: 1.1, marginTop: 22, color: BLUE },
  subtitle: { fontSize: 9, color: "#333333", marginTop: 6 },
  band: { backgroundColor: "#f5f5f5", borderLeft: `3 solid ${BLUE}`, padding: 10, marginTop: 16 },
  bandText: { fontSize: 8.5, color: "#333333" },
  h2: { fontFamily: "Garamond", fontSize: 16, color: BLUE, marginTop: 20, marginBottom: 6 },
  p: { marginBottom: 6 },
  row: { flexDirection: "row", marginBottom: 6 }, num: { width: 24, fontFamily: "Garamond", fontSize: 13, color: BLUE }, cell: { flex: 1 },
  cite: { fontSize: 7.5, color: "#666666", marginTop: 1 },
  gRow: { flexDirection: "row", marginBottom: 5 }, gCode: { width: 92, fontWeight: 600 },
  facts: { flexDirection: "row", marginTop: 14, borderTop: "1 solid #d9dde3", borderBottom: "1 solid #d9dde3", paddingVertical: 8 },
  fact: { flex: 1, paddingRight: 10 }, factLabel: { fontSize: 7.5, color: "#666666" }, factValue: { fontFamily: "Garamond", fontSize: 14, color: BLUE },
  footer: { position: "absolute", bottom: 26, left: 54, right: 54, flexDirection: "row", justifyContent: "space-between", fontSize: 7.5, color: "#666666", borderTop: "1 solid #d9dde3", paddingTop: 6 },
});
const fmtMoney = (v: any) => { const n = Number(v ?? 0); return n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}K` : n < 10 ? `$${n.toFixed(2)}` : `$${Math.round(n)}`; };
const ordinal = (n: number) => { const v = Math.round(n); const s = ["th", "st", "nd", "rd"], k = v % 100; return `${v}${s[(k - 20) % 10] ?? s[k] ?? s[0]}`; };
const clean = (s: any) => String(s ?? "").replace(/—/g, ", ").replace(/–/g, " to ").replace(/_/g, " ");
const h = React.createElement;
function Doc({ p, status }: { p: any; status: string }) {
  const ev = new Map<number, any>((p.evidence ?? []).map((e: any) => [e.id, e]));
  const drafted = String(p.model ?? "").startsWith("claude") ? "Drafted by Claude from the cited public records and checked against them" : "Assembled from the cited public records";
  const when = String(p.generated_at ?? "").slice(0, 10);
  const statusText: Record<string, string> = { draft: "Draft for reviewer", accepted: "Accepted by reviewer", rejected: "Rejected by reviewer", needs_info: "Records requested" };
  return h(Document, { title: clean(p.title), author: "Verity", subject: "Referral candidate packet" },
    h(Page, { size: "LETTER", style: S.page },
      h(View, { style: S.brandRow }, h(Text, { style: S.brand }, "VERITY"), h(Text, { style: S.brandSub }, "Provider integrity from public records")),
      h(Text, { style: S.title }, clean(p.title)),
      h(Text, { style: S.subtitle }, `${statusText[status] ?? status}. Prepared ${when}. ${drafted}.`),
      h(View, { style: S.facts },
        h(View, { style: S.fact }, h(Text, { style: S.factLabel }, "Subject"), h(Text, { style: S.factValue }, p.subject_type === "cluster" ? `Provider network ${p.subject_id}` : `NPI ${p.subject_id}`)),
        h(View, { style: S.fact }, h(Text, { style: S.factLabel }, "Findings"), h(Text, { style: S.factValue }, String((p.findings ?? []).length))),
        h(View, { style: S.fact }, h(Text, { style: S.factLabel }, "Public records cited"), h(Text, { style: S.factValue }, String((p.evidence ?? []).length))),
        h(View, { style: S.fact }, h(Text, { style: S.factLabel }, "Regulations"), h(Text, { style: S.factValue }, String((p.grounds ?? []).length)))),
      h(View, { style: S.band }, h(Text, { style: S.bandText }, "This packet describes public records and dates. It does not assert fraud, intent or guilt. Each finding cites the numbered records at the end, and the section Rule out first lists the ordinary explanations a reviewer must eliminate before any action.")),
      h(Text, { style: S.h2 }, "Summary"), h(Text, { style: S.p }, clean(p.summary)),
      h(Text, { style: S.h2 }, "Description"), h(Text, { style: S.p }, clean(p.plain_english)),
      h(Text, { style: S.h2 }, "What the records show"),
      ...(p.findings ?? []).map((f: any, i: number) => h(View, { style: S.row, key: i, minPresenceAhead: 40 }, h(Text, { style: S.num }, String(i + 1).padStart(2, "0")), h(View, { style: S.cell }, h(Text, null, clean(f.text)), h(Text, { style: S.cite }, "Records " + (f.evidence_ids ?? []).map((n: number) => `${n + 1} (${clean(ev.get(n)?.source ?? "")})`).join(", "))))),
      h(Text, { style: S.h2 }, "Regulations this relates to"),
      ...(p.grounds ?? []).map((g: any) => h(View, { style: S.gRow, key: g.cfr }, h(Text, { style: S.gCode }, `42 CFR ${g.cfr}`), h(Text, { style: S.cell }, clean(g.text).replace(/^42 CFR [^:]+:\s*/, "")))),
      h(Text, { style: S.h2 }, "Recommended next step"), h(Text, { style: S.p }, clean(p.recommendation)),
      (p.procedures ?? []).length ? h(Text, { style: S.h2 }, "Procedures behind the dollars") : null,
      ...(p.procedures ?? []).map((c: any, i: number) => h(View, { style: { flexDirection: "row", marginBottom: 5, alignItems: "flex-start" }, key: "p" + i },
        h(Text, { style: { width: 52, fontWeight: 600 } }, String(c.code)),
        h(View, { style: { flex: 1, paddingRight: 8 } }, h(Text, { style: { fontSize: 8.5 } }, `${c.program}: ${clean(c.description || "Medicaid service code")}`),
          h(Text, { style: S.cite }, c.percentile != null ? `${ordinal(Number(c.percentile) * 100)} percentile of providers on this code, ${fmtMoney(c.per_patient_month)} per patient-month against a typical ${fmtMoney(c.typical)}${c.high_vector ? "; code family with a history of abuse" : ""}` : c.charge_ratio != null ? `Submitted charge ${Number(c.charge_ratio).toFixed(1)} times the allowed amount${c.peer_ratio != null ? `, usual ${Number(c.peer_ratio).toFixed(1)} times` : ""}` : "")),
        h(View, { style: { width: 120 } }, h(Text, { style: { fontSize: 8.5, textAlign: "right" } }, `${fmtMoney(c.paid)}  ${Math.round(Number(c.share) * 100)}%`),
          h(View, { style: { height: 4, backgroundColor: "#e8edf4", marginTop: 2 } }, h(View, { style: { height: 4, width: `${Math.max(2, Math.min(100, Number(c.share) * 100))}%`, backgroundColor: BLUE } }))))),
      (p.caveats ?? []).length ? h(Text, { style: S.h2 }, "Rule out first") : null,
      ...(p.caveats ?? []).map((c: string, i: number) => h(View, { style: S.row, key: "c" + i }, h(Text, { style: S.num }, ","), h(Text, { style: S.cell }, clean(c)))),
      h(Text, { style: S.h2, break: true }, "Public records cited"),
      ...(p.evidence ?? []).map((e: any) => h(View, { style: S.row, key: "e" + e.id, minPresenceAhead: 30 }, h(Text, { style: { width: 24, fontSize: 8.5, color: BLUE, fontFamily: "Garamond" } }, String(e.id + 1)), h(View, { style: S.cell }, h(Text, { style: { fontSize: 8.5 } }, clean(e.statement)), h(Text, { style: S.cite }, clean(e.source))))),
      h(View, { style: S.footer, fixed: true }, h(Text, { style: { fontFamily: "Garamond", letterSpacing: 2, color: BLUE } }, "VERITY"), h(Text, null, "Indicators from public records, not findings"), h(Text, { render: ({ pageNumber, totalPages }: any) => `Page ${pageNumber} of ${totalPages}` })),
    ));
}
export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; if (!UUID_RE.test(id)) return NextResponse.json({ error: "not found" }, { status: 404 }); fonts();
  const { data } = await serviceClient().from("packets").select("id,status,packet").eq("id", id).maybeSingle();
  if (!data) return NextResponse.json({ error: "not found" }, { status: 404 });
  const buf = await renderToBuffer(h(Doc, { p: data.packet, status: data.status }) as any);
  return new NextResponse(new Uint8Array(buf), { headers: { "Content-Type": "application/pdf", "Content-Disposition": `inline; filename="verity-referral-${String(data.packet?.subject_id ?? id).replace(/[^A-Za-z0-9-]/g, "")}.pdf"` } });
}

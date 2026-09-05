import { NextResponse } from "next/server";
import React from "react";
import path from "path";
import { Document, Page, Text, View, StyleSheet, Font, renderToBuffer } from "@react-pdf/renderer";
import { serviceClient } from "@/lib/supabase";
export const runtime = "nodejs";
const F = (p: string) => path.join(process.cwd(), "node_modules/@fontsource", p);
let registered = false;
function fonts() {
  if (registered) return; registered = true;
  Font.register({ family: "Caslon", fonts: [{ src: F("libre-caslon-condensed/files/libre-caslon-condensed-latin-400-normal.woff") }, { src: F("libre-caslon-condensed/files/libre-caslon-condensed-latin-700-normal.woff"), fontWeight: 700 }] });
  Font.register({ family: "Inter", fonts: [{ src: F("inter/files/inter-latin-400-normal.woff") }, { src: F("inter/files/inter-latin-600-normal.woff"), fontWeight: 600 }] });
  Font.registerHyphenationCallback(w => [w]);
}
const S = StyleSheet.create({
  page: { paddingTop: 48, paddingBottom: 56, paddingHorizontal: 52, fontFamily: "Inter", fontSize: 9.5, color: "#0b0b0c", lineHeight: 1.45 },
  eyebrow: { fontSize: 8, letterSpacing: 1.2, textTransform: "uppercase", color: "#0f6e56", fontWeight: 600 },
  h1: { fontFamily: "Caslon", fontSize: 30, lineHeight: 1.05, marginTop: 8 },
  h2: { fontFamily: "Caslon", fontSize: 17, marginTop: 18, marginBottom: 6, borderBottom: "1 solid #0b0b0c", paddingBottom: 3 },
  meta: { fontSize: 8, color: "#6b6b70", marginTop: 6 },
  p: { marginBottom: 6 }, small: { fontSize: 8, color: "#48484d" },
  row: { flexDirection: "row", marginBottom: 4 }, num: { width: 22, fontFamily: "Caslon", fontSize: 12, color: "#0f6e56" }, cell: { flex: 1 },
  cite: { fontSize: 7.5, color: "#6b6b70" },
  box: { border: "1 solid #e4e4e0", padding: 10, marginTop: 6, backgroundColor: "#f6f6f4" },
  footer: { position: "absolute", bottom: 24, left: 52, right: 52, flexDirection: "row", justifyContent: "space-between", fontSize: 7.5, color: "#6b6b70", borderTop: "1 solid #e4e4e0", paddingTop: 6 },
});
const clean = (s: any) => String(s ?? "").replace(/—/g, ", ").replace(/–/g, " to ");
const h = React.createElement;
function Doc({ p, id, status }: { p: any; id: string; status: string }) {
  const ev = new Map<number, any>((p.evidence ?? []).map((e: any) => [e.id, e]));
  return h(Document, { title: clean(p.title), author: "Verity", subject: "Referral candidate packet" },
    h(Page, { size: "LETTER", style: S.page },
      h(Text, { style: S.eyebrow }, "Verity, referral candidate packet"),
      h(Text, { style: S.h1 }, clean(p.title)),
      h(Text, { style: S.meta }, `Packet ${id}  ·  status ${status}  ·  generated ${String(p.generated_at ?? "").slice(0, 16).replace("T", " ")} UTC  ·  drafted by ${clean(p.model)}`),
      h(View, { style: S.box }, h(Text, { style: S.small }, "This document describes public records and dates. It does not assert fraud, intent or guilt. Every finding cites the evidence rows listed at the end, and the caveats list the ordinary explanations a reviewer must rule out before any action. Verify each cited row against the source dataset.")),
      h(Text, { style: S.h2 }, "Summary"), h(Text, { style: S.p }, clean(p.summary)),
      h(Text, { style: S.h2 }, "In plain language"), h(Text, { style: S.p }, clean(p.plain_english)),
      h(Text, { style: S.h2 }, "Findings"),
      ...(p.findings ?? []).map((f: any, i: number) => h(View, { style: S.row, key: i, wrap: false }, h(Text, { style: S.num }, String(i + 1).padStart(2, "0")), h(View, { style: S.cell }, h(Text, null, clean(f.text)), h(Text, { style: S.cite }, "Evidence " + (f.evidence_ids ?? []).map((n: number) => `[${n}] ${ev.get(n)?.source ?? ""}`).join("; "))))),
      h(Text, { style: S.h2 }, "Regulatory grounds"),
      ...(p.grounds ?? []).map((g: any) => h(View, { style: S.row, key: g.cfr }, h(Text, { style: { width: 90, fontWeight: 600 } }, `42 CFR ${g.cfr}`), h(Text, { style: S.cell }, clean(g.text)))),
      h(Text, { style: S.h2 }, "Recommendation"), h(Text, { style: S.p }, clean(p.recommendation)),
      (p.caveats ?? []).length ? h(Text, { style: S.h2 }, "Caveats to rule out first") : null,
      ...(p.caveats ?? []).map((c: string, i: number) => h(View, { style: S.row, key: "c" + i }, h(Text, { style: S.num }, "·"), h(Text, { style: S.cell }, clean(c)))),
      h(Text, { style: S.h2, break: true }, "Evidence trail"),
      ...(p.evidence ?? []).map((e: any) => h(View, { style: S.row, key: "e" + e.id, wrap: false }, h(Text, { style: { width: 26, fontSize: 8, color: "#0f6e56" } }, `[${e.id}]`), h(View, { style: S.cell }, h(Text, { style: { fontSize: 8.5 } }, clean(e.statement)), h(Text, { style: S.cite }, clean(e.source))))),
      h(View, { style: S.footer, fixed: true }, h(Text, null, "Verity  ·  indicators from public data, not findings  ·  Sahaj Satani and Rohan Sanghavi"), h(Text, { render: ({ pageNumber, totalPages }: any) => `${pageNumber} / ${totalPages}` })),
    ));
}
export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; fonts();
  const { data } = await serviceClient().from("packets").select("id,status,packet").eq("id", id).maybeSingle();
  if (!data) return NextResponse.json({ error: "not found" }, { status: 404 });
  const buf = await renderToBuffer(h(Doc, { p: data.packet, id, status: data.status }) as any);
  return new NextResponse(new Uint8Array(buf), { headers: { "Content-Type": "application/pdf", "Content-Disposition": `inline; filename="verity-packet-${id.slice(0, 8)}.pdf"` } });
}

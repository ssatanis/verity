import { Nav } from "@/components/landing/Nav";
import { Hero, WhatWeDo, Stats, Detectors, Hierarchy, WhoWeServe, HowItWorks, Security, CTA, ScrollProgress, BackToTop } from "@/components/landing/Sections";
import { Footer } from "@/components/landing/Footer";
import { publicClient } from "@/lib/supabase";
import { withFallback } from "@/lib/fallback";
export const revalidate = 300;
export default async function Landing() {
  const rows = await withFallback<any[]>("summary", () => publicClient().from("summary").select("key,value").eq("key", "totals"), r => [{ key: "totals", value: r }]);
  const stats = (rows?.[0]?.value as Record<string, any>) ?? {};
  // Dollars paid after the action by year of the action (Detector 3 summary), from 2010 on
  const d3 = await withFallback<any[]>("summary", () => publicClient().from("summary").select("key,value").eq("key", "d3_summary"), r => r.filter((x: any) => x.key === "d3_summary"));
  const byYear = (((d3?.[0]?.value as any)?.by_year ?? []) as string[][]).map(r => [r[0], Number(r[1]), Number(r[2])] as [string, number, number]).filter(r => Number(r[0]) >= 2010 && Number(r[0]) <= 2024);
  // Candidates per tier: a head count per tier from provider_risk, falling back to the totals row
  const tierCounts = await Promise.all([1, 2, 3, 4, 5].map(async t => {
    try { const { count, error } = await publicClient().from("provider_risk").select("npi", { count: "exact", head: true }).eq("tier", t); if (!error && count != null) return count; } catch {}
    return Number(stats[`risk_tier${t}`] ?? NaN);
  }));
  return (
    <div className="min-h-screen bg-white">
      <ScrollProgress />
      <Nav />
      <Hero />
      <WhatWeDo />
      <Stats stats={stats} byYear={byYear} />
      <Detectors />
      <Hierarchy tierCounts={tierCounts.every(n => Number.isFinite(n)) ? tierCounts : []} />
      <WhoWeServe />
      <HowItWorks />
      <Security />
      <CTA />
      <Footer />
      <BackToTop />
    </div>
  );
}

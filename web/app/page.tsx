import { Nav } from "@/components/landing/Nav";
import { Hero, WhatWeDo, Stats, Detectors, Hierarchy, WhoWeServe, HowItWorks, Security, CTA } from "@/components/landing/Sections";
import { Footer } from "@/components/landing/Footer";
import { publicClient } from "@/lib/supabase";
import { withFallback } from "@/lib/fallback";
export const revalidate = 300;
export default async function Landing() {
  const rows = await withFallback<any[]>("summary", () => publicClient().from("summary").select("key,value").eq("key", "totals"), r => [{ key: "totals", value: r }]);
  const stats = (rows?.[0]?.value as Record<string, any>) ?? {};
  return (
    <div className="min-h-screen bg-white">
      <Nav />
      <Hero />
      <WhatWeDo />
      <Stats stats={stats} />
      <Detectors />
      <Hierarchy />
      <WhoWeServe />
      <HowItWorks />
      <Security />
      <CTA />
      <Footer />
    </div>
  );
}

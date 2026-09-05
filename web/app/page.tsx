import { Nav } from "@/components/landing/Nav";
import { Hero, Buyers, Detectors, Hierarchy, Pipeline, Sources, CTA } from "@/components/landing/Sections";
import { Footer } from "@/components/landing/Footer";
import { publicClient } from "@/lib/supabase";
export const revalidate = 300;
export default async function Landing() {
  let stats: Record<string, any> = {};
  try { const { data } = await publicClient().from("summary").select("key,value").eq("key", "totals").maybeSingle(); stats = (data?.value as Record<string, any>) ?? {}; } catch {}
  return (
    <div className="min-h-screen">
      <Nav />
      <Hero stats={stats} />
      <Detectors stats={stats} />
      <Hierarchy />
      <Buyers />
      <Pipeline />
      <Sources />
      <CTA />
      <Footer />
    </div>
  );
}

import Link from "next/link";
import { Nav } from "@/components/landing/Nav";
import { ProductMock } from "@/components/landing/ProductMock";
import { ContinuouslyRunning, InProduction, Automation, Explore, Footer } from "@/components/landing/Sections";
import { publicClient } from "@/lib/supabase";

export const revalidate = 300;

export default async function Landing() {
  let stats: Record<string, any> = {};
  try {
    const { data } = await publicClient().from("summary").select("key,value").eq("key", "totals").maybeSingle();
    stats = (data?.value as Record<string, any>) ?? {};
  } catch {}
  return (
    <div className="min-h-screen py-8 px-4 md:px-10">
      <div className="frame max-w-[1160px] mx-auto overflow-hidden">
        <Nav />
        <section className="grid md:grid-cols-2 gap-10 items-center px-10 pt-12 pb-16">
          <div>
            <h1 className="serif text-[52px] md:text-[60px] leading-[0.98]">Real-time detection and incident response</h1>
            <p className="text-[14px] text-[var(--ink-2)] mt-6 max-w-md leading-6">Automate program integrity from insight to action with Verity powering Medicaid, Medicare, fraud and payment integrity teams.</p>
            <Link href="/app" className="btn-dark mt-7">Open console</Link>
          </div>
          <ProductMock />
        </section>
        <div className="mx-6 border-t border-[var(--line)]" />
        <ContinuouslyRunning />
        <div className="mx-6 border-t border-[var(--line)]" />
        <InProduction stats={stats} />
        <div className="mx-6 border-t border-[var(--line)] mt-10" />
        <Automation />
        <div className="mx-6 border-t border-[var(--line)]" />
        <Explore />
        <Footer />
      </div>
    </div>
  );
}

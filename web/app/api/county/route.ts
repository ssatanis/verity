import { NextResponse } from "next/server";
import { publicClient } from "@/lib/supabase";
export async function GET(req: Request) {
  const fips = (new URL(req.url).searchParams.get("fips") ?? "").padStart(5, "0");
  if (!/^\d{5}$/.test(fips)) return NextResponse.json({ rows: [] });
  const { data } = await publicClient().from("provider_risk").select("npi,name,tier,dollars_at_risk,reasons").eq("county_fips", fips).order("rank").limit(8);
  return NextResponse.json({ rows: data ?? [] });
}

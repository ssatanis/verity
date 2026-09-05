import { publicClient } from "@/lib/supabase";
import { PacketPanel } from "@/components/app/PacketPanel";
export default async function Packet({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { data: p } = await publicClient().from("packets").select("*").eq("id", id).maybeSingle();
  if (!p) return <div>Not found</div>;
  return <div className="max-w-3xl"><div className="eyebrow mb-3">Packet</div><PacketPanel subjectType={p.subject_type} subjectId={p.subject_id} existing={[p]} /></div>;
}

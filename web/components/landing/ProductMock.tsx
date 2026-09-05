export function ProductMock({ runs }: { runs?: { name: string; pct: number }[] }) {
  const r = runs ?? [{ name: "Ghost networks", pct: 62 }, { name: "Impossible days", pct: 54 }, { name: "Revoked but paid", pct: 47 }];
  return (
    <div className="relative rounded-[18px] overflow-hidden" style={{ background: "linear-gradient(135deg,#0b0b0d 0%,#2a2a2e 55%,#d9d9dd 100%)" }}>
      <div className="absolute inset-0 opacity-60" style={{ background: "repeating-linear-gradient(115deg, transparent 0 34px, rgba(255,255,255,.06) 34px 36px)" }} />
      <div className="relative m-4 ml-8 mt-8 rounded-tl-[14px] bg-white shadow-2xl overflow-hidden" style={{ minHeight: 360 }}>
        <div className="flex">
          <aside className="w-10 border-r border-[var(--line)] py-3 flex flex-col items-center gap-3 text-[var(--ink-3)]">
            <span className="w-5 h-5 rounded-md bg-[var(--ink)] grid place-items-center text-white text-[10px]">v</span>
            {["⌂", "◔", "⌕", "⚙", "◫"].map((g, i) => <span key={i} className="text-[11px]">{g}</span>)}
          </aside>
          <div className="flex-1 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-[11px] font-medium">Home</div>
              <div className="text-[9px] text-[var(--ink-3)] border border-[var(--line)] rounded-md px-2 py-[2px] w-40">Search Verity</div>
            </div>
            <div className="card p-3 mb-4">
              <div className="text-[10px] font-medium mb-2">Alert resolution flow</div>
              <div className="grid grid-cols-4 gap-2 text-[8px]">
                <div className="rounded-lg bg-[#2a2a2e] text-white p-2 flex flex-col justify-between"><span className="opacity-60">Ingestion</span><span className="text-[9px]">Verity alerts</span></div>
                <div className="rounded-lg p-2 grad-violet flex flex-col gap-1"><span className="text-[var(--ink-3)]">Enrichment</span>{["Critical", "High", "Medium"].map(s => <span key={s} className="bg-white/80 rounded px-1 py-[1px]">{s}</span>)}</div>
                <div className="rounded-lg p-2 bg-[#cdeee0] flex flex-col gap-1"><span className="text-[var(--ink-3)]">Investigation</span><span className="bg-white/80 rounded px-1 py-[1px]">Human review</span><span className="bg-white/80 rounded px-1 py-[1px]">Confirm incidence</span></div>
                <div className="rounded-lg p-2 bg-[#f8d7d3] flex flex-col gap-1"><span className="text-[var(--ink-3)]">Decision</span><span className="bg-white/80 rounded px-1 py-[1px]">Referral packet</span><span className="bg-white/80 rounded px-1 py-[1px]">Payment hold</span></div>
              </div>
            </div>
            <div className="text-[10px] font-medium mb-2">Runs</div>
            <div className="grid grid-cols-3 gap-2">
              {r.map(x => (
                <div key={x.name} className="card p-2">
                  <div className="text-[9px] font-medium truncate">{x.name}</div>
                  <span className="inline-block mt-1 text-[7px] text-white bg-[var(--green)] rounded-full px-[6px] py-[1px]">Active</span>
                  <div className="text-[9px] mt-2">{x.pct}%</div>
                  <div className="h-[3px] bg-[var(--line)] rounded mt-1"><div className="h-[3px] bg-[var(--ink)] rounded" style={{ width: `${x.pct}%` }} /></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

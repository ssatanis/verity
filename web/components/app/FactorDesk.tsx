import { money } from "@/lib/labels";
type Row = { factor: string; family: string; label: string; unit: string; direction: string; note: string; value: number | null; percentile: number | null; z: number | null; outlook?: string | null };
const FAM: Record<string, string> = { formation: "Formation timing", ownership: "Ownership", addresses: "Addresses and contacts", lists: "List exposure", market: "Market", money: "Money", identity: "Identity and enrollment" };
const fmt = (r: Row) => { const v = r.value; if (v == null) return "n/a"; if (r.unit === "$") return money(v); if (r.unit === "share") return `${Math.round(v * 100)}%`; if (r.unit === "years") return `${v.toFixed(1)} y`; if (r.unit === "flag") return v ? "yes" : "no"; if (r.unit === "ratio") return v.toFixed(2); if (r.unit === "per 10k") return v.toFixed(1); return Number.isInteger(v) ? String(v) : v.toFixed(1); };
export function FactorDesk({ rows }: { rows: Row[] }) {
  if (!rows?.length) return null;
  const mom = rows.find(r => r.factor === "momentum");
  const fams = Object.keys(FAM).map(f => [f, rows.filter(r => r.family === f)] as const).filter(([, rs]) => rs.length);
  const movers = rows.filter(r => r.factor !== "momentum" && r.percentile != null && r.percentile >= 90).sort((a, b) => (b.percentile ?? 0) - (a.percentile ?? 0)).slice(0, 5);
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div><h2 className="serif text-[24px]">Factor desk</h2><p className="text-[12.5px] text-[var(--ink-3)] mt-1 max-w-2xl">Thirty measurable factors for this network, each with its value, its percentile among all networks in the risky direction, and how far it sits from the typical network. Nothing here is a finding.</p></div>
        {mom && <div className="kpi min-w-[220px]"><div className="eyebrow">Momentum, indicative</div><div className="serif text-[30px]" style={{ color: "var(--blue)" }}>{mom.outlook ? mom.outlook[0].toUpperCase() + mom.outlook.slice(1) : "n/a"}</div><div className="text-[11px] text-[var(--ink-3)]">z {mom.value?.toFixed(2)}{mom.percentile != null ? `, percentile ${Math.round(mom.percentile)}` : ""}. Rate-of-change factors only; not a validated forecast.</div></div>}
      </div>
      {movers.length > 0 && <div className="mt-4 flex flex-wrap gap-2">{movers.map(m => <span key={m.factor} className="tag tag-accent">{m.label}: {fmt(m)} (top {Math.max(1, Math.round(100 - (m.percentile ?? 0)))}%)</span>)}</div>}
      <div className="grid md:grid-cols-2 gap-x-8 mt-4">
        {fams.map(([f, rs]) => (
          <div key={f} className="mb-4">
            <div className="eyebrow mb-1">{FAM[f]}</div>
            <table className="table"><tbody>{rs.map(r => (
              <tr key={r.factor} title={r.note}><td className="text-[var(--ink-2)] w-[55%]">{r.label}</td><td className="text-right">{fmt(r)}</td>
                <td className="w-[90px]"><div className="h-[6px] bg-[var(--paper-2)]"><div className="h-[6px]" style={{ width: `${Math.max(2, r.percentile ?? 0)}%`, background: (r.percentile ?? 0) >= 90 ? "var(--blue)" : "#7f93ab" }} /></div></td>
                <td className="text-right text-[11px] text-[var(--ink-3)] w-[46px]">{r.percentile != null ? `${Math.round(r.percentile)}th` : ""}</td></tr>))}</tbody></table>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-[var(--ink-3)] mt-2">Percentile bars show where this network sits among all networks with three or more providers; the risky direction is always to the right. Values come from CMS enrollment and ownership files, the national provider registry, T-MSIS Medicaid spending, and CMS market saturation.</p>
    </div>
  );
}

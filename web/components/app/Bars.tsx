// Small, dependency-free bar chart in the three-colour palette.
export function Bars({ rows, unit = "", max, height = 180 }: { rows: [string, number, string?][]; unit?: string; max?: number; height?: number }) {
  const m = max ?? Math.max(...rows.map(r => r[1]), 1);
  return (
    <div className="flex items-end gap-3" style={{ height }}>
      {rows.map(([label, v, note]) => (
        <div key={label} className="flex-1 flex flex-col items-center justify-end h-full">
          <div className="text-[11px] mb-1" style={{ color: "var(--blue)" }}>{typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString() : v.toFixed(2)) : v}{unit}</div>
          <div className="w-full" style={{ height: `${Math.max(2, (100 * v) / m)}%`, background: "var(--blue)" }} title={note} />
          <div className="text-[11px] mt-2 text-center text-[var(--ink-2)]">{label}</div>
        </div>
      ))}
    </div>
  );
}

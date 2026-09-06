// Static SVG figures for the landing page. Server-rendered, no client state, Flag Blue palette from globals.css.
const BLUE = "#002856", LINE = "#d9dde3", INK2 = "#333333", INK3 = "#666666", TINT = "#e8edf4", PAPER = "#ffffff";
const num = (v: number) => Number(v ?? 0).toLocaleString();

// Candidates by tier: one bar per tier, linear scale, count printed beside each bar.
export function TierFigure({ counts }: { counts: number[] }) {
  const max = Math.max(1, ...counts); const labels = ["1", "2", "3", "4", "5"];
  const w = 520, rowH = 34, left = 34, barW = 380, h = rowH * 5 + 8;
  return (
    <figure className="mt-10">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Referral candidates by tier">
        {counts.map((c, i) => { const y = i * rowH + 4; const bw = Math.max(2, Math.round((c / max) * barW)); return (
          <g key={i}>
            <text x={0} y={y + 20} fontFamily="EB Garamond, Garamond, serif" fontSize="22" fill={BLUE}>{labels[i]}</text>
            <rect x={left} y={y + 4} width={barW} height={20} fill={TINT} />
            <rect x={left} y={y + 4} width={bw} height={20} fill={i === 0 ? BLUE : i === 1 ? "#3a5a86" : i === 2 ? "#7a90b0" : i === 3 ? "#aab8cc" : "#c9d2df"} />
            <text x={left + bw + 8} y={y + 19} fontFamily="Open Sans, Helvetica, Arial, sans-serif" fontSize="12" fill={INK2}>{num(c)}</text>
          </g>); })}
      </svg>
      <figcaption className="text-[12px] leading-5 mt-2" style={{ color: INK3 }}>Referral candidates by tier, every provider counted once. The tiers with documented actions and impossible volume are small by design; network tiers hold the volume.</figcaption>
    </figure>
  );
}

// Dollars Medicaid paid after a screening trigger, by the year of the action.
export function PaidAfterFigure({ rows }: { rows: [string, number, number][] }) {
  const w = 720, h = 220, top = 24, bottom = 40, left = 8, right = 8;
  const plotW = w - left - right, plotH = h - top - bottom;
  const max = Math.max(1, ...rows.map(r => r[2]));
  const slot = plotW / rows.length, bw = Math.min(40, slot * 0.6);
  return (
    <figure className="mt-16 rule pt-12">
      <div className="grid md:grid-cols-[1fr_3fr] gap-12">
        <div className="text-[17px]" style={{ color: BLUE }}>Paid after the action</div>
        <div>
          <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Medicaid dollars paid after a screening trigger, by year of the action">
            <line x1={left} y1={top + plotH} x2={w - right} y2={top + plotH} stroke={LINE} />
            {rows.map(([yr, n, m], i) => { const bh = Math.round((m / max) * plotH); const x = left + i * slot + (slot - bw) / 2; const y = top + plotH - bh; return (
              <g key={yr}>
                <rect x={x} y={y} width={bw} height={bh} fill={BLUE} />
                <text x={x + bw / 2} y={y - 6} textAnchor="middle" fontFamily="Open Sans, Helvetica, Arial, sans-serif" fontSize="11" fill={INK2}>${m.toFixed(1)}M</text>
                <text x={x + bw / 2} y={top + plotH + 16} textAnchor="middle" fontFamily="Open Sans, Helvetica, Arial, sans-serif" fontSize="11" fill={INK2}>{yr}</text>
                <text x={x + bw / 2} y={top + plotH + 31} textAnchor="middle" fontFamily="Open Sans, Helvetica, Arial, sans-serif" fontSize="10" fill={INK3}>{n} NPIs</text>
              </g>); })}
          </svg>
          <figcaption className="text-[12px] leading-5 mt-3 max-w-2xl" style={{ color: INK3 }}>Medicaid dollars paid to a provider after the exclusion, revocation or state action, grouped by the year of the action, with the number of providers under each bar. The spending file ends in December 2024, so recent actions have had less time to accumulate payments.</figcaption>
        </div>
      </div>
    </figure>
  );
}

// Three detector glyphs: a network, a clock past 24 hours, a list with a payment after it.
export function DetectorGlyph({ kind }: { kind: "network" | "clock" | "list" }) {
  const common = { width: 64, height: 64, viewBox: "0 0 64 64", fill: "none", stroke: BLUE, strokeWidth: 1.5 } as const;
  if (kind === "network") return (
    <svg {...common} role="img" aria-label="Network of providers sharing an owner">
      <circle cx="32" cy="32" r="6" fill={BLUE} /><circle cx="10" cy="14" r="4" /><circle cx="54" cy="12" r="4" /><circle cx="12" cy="52" r="4" /><circle cx="52" cy="50" r="4" /><circle cx="56" cy="32" r="4" />
      <path d="M27 28 L13 17 M37 28 L51 15 M28 36 L15 49 M36 36 L49 47 M38 32 L52 32" />
    </svg>);
  if (kind === "clock") return (
    <svg {...common} role="img" aria-label="Clock with more hours than a day holds">
      <circle cx="32" cy="32" r="24" /><path d="M32 12 L32 32 L46 40" strokeWidth="2" />
      <path d="M32 32 L18 44 M32 32 L44 18 M32 32 L20 20" strokeOpacity="0.45" />
      <path d="M8 32 A24 24 0 0 1 32 8" stroke={BLUE} strokeWidth="4" />
    </svg>);
  return (
    <svg {...common} role="img" aria-label="Exclusion list followed by a payment">
      <rect x="8" y="8" width="26" height="36" /><path d="M13 16 H29 M13 22 H29 M13 28 H23" /><path d="M13 36 L17 40 L25 32" strokeWidth="2" />
      <path d="M36 26 H54 M50 22 L54 26 L50 30" strokeWidth="2" />
      <rect x="40" y="36" width="18" height="12" /><circle cx="49" cy="42" r="3" />
    </svg>);
}

// The pipeline: public records in, a defensible packet out, with the reviewer's decision feeding back.
export function PipelineFigure() {
  const boxes = [["Public records", "federal and state"], ["Warehouse", "one NPI key"], ["Three detectors", "D1 · D2 · D3"], ["One hierarchy", "tiers 1 to 5"], ["Packet", "every line cited"], ["Reviewer", "accept or reject"]];
  const w = 1080, h = 150, bw = 150, bh = 62, gap = (w - boxes.length * bw) / (boxes.length - 1), y = 28;
  return (
    <figure className="mt-16">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Pipeline from public records to a reviewed packet">
        {boxes.map(([t, s], i) => { const x = i * (bw + gap); const last = i === boxes.length - 1; return (
          <g key={t}>
            <rect x={x} y={y} width={bw} height={bh} fill={last ? BLUE : PAPER} stroke={last ? BLUE : LINE} />
            <text x={x + bw / 2} y={y + 27} textAnchor="middle" fontFamily="EB Garamond, Garamond, serif" fontSize="19" fill={last ? PAPER : BLUE}>{t}</text>
            <text x={x + bw / 2} y={y + 47} textAnchor="middle" fontFamily="Open Sans, Helvetica, Arial, sans-serif" fontSize="11" fill={last ? PAPER : INK3}>{s}</text>
            {!last && <path d={`M${x + bw + 4} ${y + bh / 2} H${x + bw + gap - 4} M${x + bw + gap - 10} ${y + bh / 2 - 5} L${x + bw + gap - 4} ${y + bh / 2} L${x + bw + gap - 10} ${y + bh / 2 + 5}`} stroke={BLUE} strokeWidth="1.5" fill="none" />}
          </g>); })}
        <path d={`M${w - bw / 2} ${y + bh} V${y + bh + 34} H${2 * (bw + gap) + bw / 2} V${y + bh + 6}`} stroke={BLUE} strokeWidth="1.5" fill="none" strokeDasharray="4 4" />
        <path d={`M${2 * (bw + gap) + bw / 2 - 5} ${y + bh + 12} L${2 * (bw + gap) + bw / 2} ${y + bh + 6} L${2 * (bw + gap) + bw / 2 + 5} ${y + bh + 12}`} stroke={BLUE} strokeWidth="1.5" fill="none" />
        <text x={(w - bw / 2 + 2 * (bw + gap) + bw / 2) / 2} y={y + bh + 48} textAnchor="middle" fontFamily="Open Sans, Helvetica, Arial, sans-serif" fontSize="11" fill={INK3}>reviewer decisions re-weight the evidence families</text>
      </svg>
    </figure>
  );
}

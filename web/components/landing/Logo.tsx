export function Logo({ size = 28, light = false }: { size?: number; light?: boolean }) {
  const c = light ? "#ffffff" : "#002856";
  return (
    <span className="inline-flex items-center gap-3" aria-label="Verity">
      <svg width={size * 1.15} height={size} viewBox="0 0 46 40" fill="none" aria-hidden="true">
        <rect x="0" y="0" width="14" height="10" fill={c} /><rect x="16" y="0" width="14" height="10" fill={c} /><rect x="32" y="0" width="14" height="10" fill={c} />
        <rect x="0" y="15" width="21" height="10" fill={c} /><rect x="25" y="15" width="21" height="10" fill={c} />
        <rect x="0" y="30" width="46" height="10" fill={c} />
      </svg>
      <span className="serif" style={{ color: c, fontSize: size * 1.25, letterSpacing: "0.14em", lineHeight: 1, fontWeight: 500 }}>VERITY</span>
    </span>
  );
}

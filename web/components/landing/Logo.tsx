export function Logo({ size = 28, light = false }: { size?: number; light?: boolean }) {
  return <span className="serif inline-block" aria-label="Verity" style={{ color: light ? "#ffffff" : "#002856", fontSize: size * 1.25, letterSpacing: "0.16em", lineHeight: 1, fontWeight: 500 }}>VERITY</span>;
}

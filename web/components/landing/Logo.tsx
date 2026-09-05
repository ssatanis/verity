export function Logo({ size = 30, withText = true, light = false }: { size?: number; withText?: boolean; light?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
        <path d="M12 1.5l1.9 6.3L20 9.6l-6.1 1.8L12 17.7l-1.9-6.3L4 9.6l6.1-1.8L12 1.5z" fill={light ? "#fff" : "#0b0b0c"} />
        <path d="M18.5 15.5l.8 2.7 2.7.8-2.7.8-.8 2.7-.8-2.7-2.7-.8 2.7-.8.8-2.7z" fill={light ? "#fff" : "#0f6e56"} />
      </svg>
      {withText && <span className="serif" style={{ fontSize: size * 0.95, lineHeight: 1, color: light ? "#fff" : "#0b0b0c" }}>Verity</span>}
    </span>
  );
}

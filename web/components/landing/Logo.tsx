export function Logo({ size = 34, withText = false }: { size?: number; withText?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-grid place-items-center rounded-[10px] bg-[var(--ink)] text-white" style={{ width: size, height: size }} aria-hidden>
        <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
          <path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6L5.6 18.4" />
        </svg>
      </span>
      {withText && <span className="serif text-[20px]">Verity</span>}
    </span>
  );
}

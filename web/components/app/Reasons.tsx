import { reasonList } from "@/lib/labels";
// The reasons behind a provider's tier, one statement to a line. `compact` is for table cells and the map panel, where the
// lines sit tight; the full form spaces them out and marks each with a rule so they read as separate statements.
export function Reasons({ text, compact = false, max }: { text?: string | null; compact?: boolean; max?: number }) {
  const all = reasonList(text);
  if (!all.length) return null;
  const list = max != null ? all.slice(0, max) : all;
  const more = all.length - list.length;
  return (
    <ul className={compact ? "space-y-0.5" : "space-y-1.5"}>
      {list.map((x, i) => (
        <li key={i} className="flex gap-2">
          <span aria-hidden className="shrink-0 mt-[7px]" style={{ width: 3, height: 3, background: "var(--ink-3)" }} />
          <span>{x}</span>
        </li>
      ))}
      {more > 0 && <li className="text-[var(--ink-3)] pl-[11px]">and {more} more</li>}
    </ul>
  );
}

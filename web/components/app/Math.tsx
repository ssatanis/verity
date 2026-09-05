"use client";
import "katex/dist/katex.min.css";
import { BlockMath, InlineMath } from "react-katex";
export function M({ children }: { children: string }) { return <InlineMath math={children} />; }
export function Eq({ children }: { children: string }) { return <div className="my-3 overflow-x-auto"><BlockMath math={children} /></div>; }

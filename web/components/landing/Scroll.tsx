"use client";
import { motion, useInView, useReducedMotion, useScroll, useSpring, useTransform, animate } from "framer-motion";
import { useEffect, useRef, useState } from "react";

// Scroll primitives for the whole site. Every one of them collapses to a static, fully visible element when the
// visitor asks for reduced motion, so nothing here is load-bearing for reading the page.

const EASE = [0.22, 1, 0.36, 1] as const;

// A thin Flag Blue rule across the very top that fills as the page scrolls, so the reader always knows where they are.
export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const x = useSpring(scrollYProgress, { stiffness: 220, damping: 40, restDelta: 0.0005 });
  return <motion.div aria-hidden className="fixed top-0 left-0 right-0 z-50 origin-left" style={{ height: 2, background: "var(--blue)", scaleX: x }} />;
}

// Moves its child against the scroll, by `speed` px over the element's full travel through the viewport.
export function Parallax({ children, speed = 60, className, style }: { children: React.ReactNode; speed?: number; className?: string; style?: React.CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], [speed, -speed]);
  const smooth = useSpring(y, { stiffness: 120, damping: 30, mass: 0.4 });
  return <motion.div ref={ref} className={className} style={{ ...style, y: reduce ? 0 : smooth }}>{children}</motion.div>;
}

// Fades and lifts a block the first time it enters the viewport.
export function Reveal({ children, delay = 0, y = 22, className, style }: { children: React.ReactNode; delay?: number; y?: number; className?: string; style?: React.CSSProperties }) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className} style={style}>{children}</div>;
  return (
    <motion.div className={className} style={style} initial={{ opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-70px" }} transition={{ duration: 0.7, ease: EASE, delay }}>
      {children}
    </motion.div>
  );
}

// Same, on mount rather than on scroll: for content already on screen when the page loads.
export function Rise({ children, delay = 0, className, style }: { children: React.ReactNode; delay?: number; className?: string; style?: React.CSSProperties }) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className} style={style}>{children}</div>;
  return <motion.div className={className} style={style} initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.85, ease: EASE, delay }}>{children}</motion.div>;
}

// A container whose direct <StaggerItem> children arrive one after another.
export function Stagger({ children, className, step = 0.09, delay = 0, style }: { children: React.ReactNode; className?: string; step?: number; delay?: number; style?: React.CSSProperties }) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className} style={style}>{children}</div>;
  return (
    <motion.div className={className} style={style} initial="hide" whileInView="show" viewport={{ once: true, margin: "-70px" }} variants={{ show: { transition: { staggerChildren: step, delayChildren: delay } } }}>
      {children}
    </motion.div>
  );
}
export function StaggerItem({ children, className, y = 26, style }: { children: React.ReactNode; className?: string; y?: number; style?: React.CSSProperties }) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className} style={style}>{children}</div>;
  return <motion.div className={className} style={style} variants={{ hide: { opacity: 0, y }, show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: EASE } } }}>{children}</motion.div>;
}

// A display heading whose lines rise in sequence behind a clipping mask.
export function Headline({ lines, className, style, delay = 0, onScroll = false, as = "h1" }: { lines: string[]; className?: string; style?: React.CSSProperties; delay?: number; onScroll?: boolean; as?: "h1" | "h2" }) {
  const reduce = useReducedMotion();
  const Tag: any = as === "h2" ? motion.h2 : motion.h1;
  const Plain: any = as;
  if (reduce) return <Plain className={className} style={style}>{lines.map((l, i) => <span key={i} className="block">{l}</span>)}</Plain>;
  const anim = onScroll ? { whileInView: "show", viewport: { once: true, margin: "-70px" } } : { animate: "show" };
  return (
    <Tag className={className} style={style} initial="hide" {...anim} variants={{ show: { transition: { staggerChildren: 0.1, delayChildren: delay } } }}>
      {lines.map((l, i) => (
        <span key={i} className="block overflow-hidden" style={{ paddingBottom: "0.06em" }}>
          <motion.span className="block" variants={{ hide: { y: "110%" }, show: { y: "0%", transition: { duration: 0.95, ease: EASE } } }}>{l}</motion.span>
        </span>
      ))}
    </Tag>
  );
}

// Counts a number up the first time it is seen. The unit is fixed by the final value, so a figure counting up never jumps
// from dollars to millions part-way. A server component cannot hand a client component a function, so the caller names a
// format rather than passing one.
export type CountFormat = "count" | "money";
function formatter(kind: CountFormat, final: number) {
  if (kind === "money") return (v: number) => final >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : final >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${Math.round(v).toLocaleString()}`;
  return (v: number) => Math.round(v).toLocaleString();
}
export function CountUp({ value, format = "count", duration = 1.5, className, style }: { value: number; format?: CountFormat; duration?: number; className?: string; style?: React.CSSProperties }) {
  const ref = useRef<HTMLSpanElement>(null);
  const seen = useInView(ref, { once: true, margin: "-80px" });
  const reduce = useReducedMotion();
  const safe = Number.isFinite(value) ? value : 0;
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const fmt = formatter(format, safe);
    if (reduce) { el.textContent = fmt(safe); return; }
    if (!seen) { el.textContent = fmt(0); return; }
    const controls = animate(0, safe, { duration, ease: [0.16, 1, 0.3, 1], onUpdate: v => { el.textContent = fmt(v); }, onComplete: () => { el.textContent = fmt(safe); } });
    return () => controls.stop();
  }, [seen, safe, reduce, duration, format]);
  return <span ref={ref} className={className} style={style}>{formatter(format, safe)(safe)}</span>;
}

// Reports which of the given section ids is the one the reader is currently in, for the header's section links.
export function useScrollSpy(ids: string[], offset = 140) {
  const [active, setActive] = useState<string | null>(null);
  const key = ids.join("|");
  useEffect(() => {
    if (!key) return;
    const list = key.split("|");
    const read = () => {
      let cur: string | null = null;
      for (const id of list) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top - offset <= 0) cur = id;
      }
      setActive(cur);
    };
    read();
    window.addEventListener("scroll", read, { passive: true });
    window.addEventListener("resize", read);
    return () => { window.removeEventListener("scroll", read); window.removeEventListener("resize", read); };
  }, [key, offset]);
  return active;
}

// True once the page has scrolled past `after` pixels.
export function useScrolled(after = 8) {
  const [past, setPast] = useState(false);
  useEffect(() => {
    const read = () => setPast(window.scrollY > after);
    read();
    window.addEventListener("scroll", read, { passive: true });
    return () => window.removeEventListener("scroll", read);
  }, [after]);
  return past;
}

// Appears once the reader is a screen down, and returns them to the top.
export function BackToTop() {
  const [show, setShow] = useState(false);
  const reduce = useReducedMotion();
  useEffect(() => {
    const read = () => setShow(window.scrollY > window.innerHeight * 0.9);
    read();
    window.addEventListener("scroll", read, { passive: true });
    return () => window.removeEventListener("scroll", read);
  }, []);
  return (
    <motion.button
      aria-label="Back to top" onClick={() => window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" })}
      initial={false} animate={{ opacity: show ? 1 : 0, y: show ? 0 : 12 }} style={{ background: "var(--blue)", color: "#fff", border: "1px solid var(--blue)", pointerEvents: show ? "auto" : "none" }}
      transition={{ duration: 0.3, ease: EASE }}
      className="fixed right-5 bottom-5 z-40 hidden md:flex items-center gap-2 px-4 py-3 text-[12px]"
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
      Top
    </motion.button>
  );
}

// Draws the stroked shapes inside once they scroll into view, by animating their dash offset.
export function DrawIn({ children, className, duration = 1.2, delay = 0, step = 0.05 }: { children: React.ReactNode; className?: string; duration?: number; delay?: number; step?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref, { once: true, margin: "-90px" });
  const reduce = useReducedMotion();
  useEffect(() => {
    const el = ref.current; if (!el || reduce) return;
    const strokes = Array.from(el.querySelectorAll<SVGGeometryElement>("path, line, polyline")).filter(p => { const f = p.getAttribute("fill"); return !f || f === "none"; });
    if (!seen) { for (const p of strokes) { try { const L = p.getTotalLength(); p.style.strokeDasharray = `${L}`; p.style.strokeDashoffset = `${L}`; } catch {} } return; }
    const stops: (() => void)[] = [];
    strokes.forEach((p, i) => {
      let L = 0; try { L = p.getTotalLength(); } catch { return; }
      if (!L) return;
      p.style.strokeDasharray = `${L}`;
      const c = animate(L, 0, { duration, delay: delay + i * step, ease: "easeInOut", onUpdate: v => { p.style.strokeDashoffset = `${v}`; }, onComplete: () => { p.style.strokeDasharray = ""; p.style.strokeDashoffset = ""; } });
      stops.push(() => c.stop());
    });
    return () => stops.forEach(f => f());
  }, [seen, reduce, duration, delay, step]);
  return <div ref={ref} className={className}>{children}</div>;
}

// Holds the hero. Its content lifts and fades as the reader scrolls past, so the section below arrives on a clean field.
export function ScrollFade({ children, className, style, lift = 90, fadeAt = 0.7 }: { children: React.ReactNode; className?: string; style?: React.CSSProperties; lift?: number; fadeAt?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], [0, -lift]);
  const opacity = useTransform(scrollYProgress, [0, fadeAt], [1, 0]);
  if (reduce) return <div ref={ref} className={className} style={style}>{children}</div>;
  return <motion.div ref={ref} className={className} style={{ ...style, y, opacity }}>{children}</motion.div>;
}

// The cue at the foot of the hero. It fades away as soon as the reader takes the hint.
export function ScrollCue({ label = "Scroll" }: { label?: string }) {
  const { scrollY } = useScroll();
  const opacity = useTransform(scrollY, [0, 220], [1, 0]);
  const reduce = useReducedMotion();
  return (
    <motion.div aria-hidden className="flex items-center gap-3 text-[11px] tracking-[0.18em] uppercase" style={{ color: "rgba(255,255,255,0.75)", opacity: reduce ? 1 : opacity }}>
      {label}
      <motion.span className="block" style={{ width: 1, height: 26, background: "rgba(255,255,255,0.55)", transformOrigin: "top" }}
        animate={reduce ? {} : { scaleY: [0.15, 1, 0.15], opacity: [0.3, 1, 0.3] }} transition={{ duration: 2.1, repeat: Infinity, ease: "easeInOut" }} />
    </motion.div>
  );
}

// A rule that draws itself down the left of a list as the list scrolls through the viewport, tying the steps together.
export function ScrollRule({ className, style }: { className?: string; style?: React.CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 85%", "end 55%"] });
  const scaleY = useSpring(scrollYProgress, { stiffness: 140, damping: 30 });
  return <div ref={ref} className={className} style={style}><motion.div style={{ width: "100%", height: "100%", background: "var(--blue)", transformOrigin: "top", scaleY: reduce ? 1 : scaleY }} /></div>;
}

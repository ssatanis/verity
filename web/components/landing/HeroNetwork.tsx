"use client";
import { useEffect, useRef } from "react";
// Animated provider network: nodes drift on their own, link to their nearest neighbours, and lean toward the cursor. Flag blue ground, white marks.
type Node = { x: number; y: number; vx: number; vy: number; r: number; hub: boolean };
export function HeroNetwork() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current; if (!canvas) return;
    const ctx = canvas.getContext("2d"); if (!ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let W = 0, H = 0, dpr = Math.min(2, window.devicePixelRatio || 1);
    const mouse = { x: -1e4, y: -1e4, active: false };
    let nodes: Node[] = []; let raf = 0; let last = performance.now();
    const seed = () => {
      const n = Math.max(40, Math.min(110, Math.round((W * H) / 14000)));
      nodes = Array.from({ length: n }, (_, i) => ({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - 0.5) * 0.25, vy: (Math.random() - 0.5) * 0.25, r: i % 7 === 0 ? 3.2 : 2, hub: i % 7 === 0 }));
    };
    const resize = () => {
      const rect = canvas.getBoundingClientRect(); W = rect.width; H = rect.height; dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); seed();
    };
    const draw = (now: number) => {
      const dt = Math.min(2.5, (now - last) / 16.7); last = now;
      const g = ctx.createLinearGradient(0, 0, W, H); g.addColorStop(0, "#0b3a78"); g.addColorStop(1, "#002856");
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      const link = Math.min(190, Math.max(110, Math.sqrt((W * H) / nodes.length) * 1.35));
      for (const p of nodes) {
        if (!reduce) {
          p.x += p.vx * dt; p.y += p.vy * dt;
          if (mouse.active) {
            const dx = mouse.x - p.x, dy = mouse.y - p.y, d2 = dx * dx + dy * dy, R = 260;
            if (d2 < R * R) { const d = Math.sqrt(d2) || 1; const f = (1 - d / R) * 0.045; p.vx += (dx / d) * f * dt; p.vy += (dy / d) * f * dt; }
          }
          p.vx *= 0.985; p.vy *= 0.985;
          const s = Math.hypot(p.vx, p.vy); if (s < 0.06) { p.vx += (Math.random() - 0.5) * 0.03; p.vy += (Math.random() - 0.5) * 0.03; } else if (s > 1.4) { p.vx *= 0.9; p.vy *= 0.9; }
          if (p.x < -20) p.x = W + 20; if (p.x > W + 20) p.x = -20; if (p.y < -20) p.y = H + 20; if (p.y > H + 20) p.y = -20;
        }
      }
      ctx.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j]; const dx = a.x - b.x, dy = a.y - b.y; const d = Math.hypot(dx, dy);
        if (d < link) { const t = 1 - d / link; ctx.strokeStyle = `rgba(255,255,255,${(0.05 + 0.3 * t).toFixed(3)})`; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
      }
      if (mouse.active) for (const p of nodes) { const d = Math.hypot(p.x - mouse.x, p.y - mouse.y); if (d < 170) { ctx.strokeStyle = `rgba(255,255,255,${(0.35 * (1 - d / 170)).toFixed(3)})`; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke(); } }
      for (const p of nodes) { ctx.fillStyle = p.hub ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.6)"; ctx.fillRect(p.x - p.r, p.y - p.r, p.r * 2, p.r * 2); }
      if (mouse.active) { ctx.fillStyle = "rgba(255,255,255,0.9)"; ctx.fillRect(mouse.x - 2.5, mouse.y - 2.5, 5, 5); }
      if (running) raf = requestAnimationFrame(draw);
    };
    const onMove = (e: PointerEvent) => { const r = canvas.getBoundingClientRect(); mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top; mouse.active = true; };
    const onLeave = () => { mouse.active = false; mouse.x = -1e4; mouse.y = -1e4; };
    // The loop only runs while the hero is actually on screen and the tab is in front, so scrolling down the page or
    // switching away costs nothing.
    let running = false, visible = true, onScreen = true;
    const play = () => { if (running || !visible || !onScreen) return; running = true; last = performance.now(); raf = requestAnimationFrame(draw); };
    const stop = () => { running = false; cancelAnimationFrame(raf); };
    const sync = () => (visible && onScreen ? play() : stop());
    const io = new IntersectionObserver(es => { onScreen = es.some(e => e.isIntersecting); sync(); }, { threshold: 0 });
    io.observe(canvas);
    const onVis = () => { visible = document.visibilityState === "visible"; sync(); };
    document.addEventListener("visibilitychange", onVis);
    const ro = new ResizeObserver(() => resize());
    ro.observe(canvas);
    resize(); window.addEventListener("resize", resize); canvas.addEventListener("pointermove", onMove); canvas.addEventListener("pointerleave", onLeave);
    play();
    return () => { stop(); io.disconnect(); ro.disconnect(); document.removeEventListener("visibilitychange", onVis); window.removeEventListener("resize", resize); canvas.removeEventListener("pointermove", onMove); canvas.removeEventListener("pointerleave", onLeave); };
  }, []);
  return <canvas ref={ref} className="absolute inset-0 w-full h-full" aria-hidden="true" />;
}

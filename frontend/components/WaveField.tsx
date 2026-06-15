"use client";

import { useEffect, useRef } from "react";

type Layer = {
  baseY: number; // fraction of height (0..1)
  amp: number; // px
  wl1: number; // primary wavelength (px)
  wl2: number; // secondary wavelength for organic interference (px)
  speed: number; // temporal flow
  phase: number;
  color: string; // "r,g,b"
  alpha: number;
  width: number;
};

// Layered swells — mostly mid/lower field so headings stay clean.
const LAYERS: Layer[] = [
  { baseY: 0.46, amp: 30, wl1: 620, wl2: 270, speed: 0.5, phase: 0.4, color: "30,201,151", alpha: 0.16, width: 1.4 },
  { baseY: 0.55, amp: 26, wl1: 540, wl2: 240, speed: 0.62, phase: 1.7, color: "30,201,151", alpha: 0.13, width: 1.3 },
  { baseY: 0.66, amp: 38, wl1: 720, wl2: 320, speed: 0.44, phase: 2.6, color: "30,201,151", alpha: 0.18, width: 1.5 },
  { baseY: 0.75, amp: 30, wl1: 600, wl2: 280, speed: 0.7, phase: 0.9, color: "74,128,255", alpha: 0.1, width: 1.3 },
  { baseY: 0.85, amp: 42, wl1: 760, wl2: 340, speed: 0.5, phase: 3.3, color: "30,201,151", alpha: 0.15, width: 1.5 },
];

export default function WaveField({ scrollTargetId }: { scrollTargetId?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scroller = scrollTargetId ? document.getElementById(scrollTargetId) : null;
    const getScroll = () => (scroller ? scroller.scrollTop : window.scrollY);

    let w = 0;
    let h = 0;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.max(1, Math.floor(w * dpr));
      canvas.height = Math.max(1, Math.floor(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const start = performance.now();
    let raf = 0;

    const render = (now: number) => {
      const t = (now - start) / 1000;
      const scroll = getScroll();
      ctx.clearRect(0, 0, w, h);

      // additive blending so overlapping swells glow softly
      ctx.globalCompositeOperation = "lighter";
      const step = 10;
      for (const L of LAYERS) {
        const baseY =
          L.baseY * h +
          Math.sin(t * 0.25 + L.phase) * 7 + // gentle self-motion
          Math.sin(scroll * 0.0015 + L.phase) * 16; // bounded scroll undulation (stays in view)

        ctx.beginPath();
        for (let x = -20; x <= w + 20; x += step) {
          const y =
            baseY +
            L.amp * Math.sin(x / L.wl1 + t * L.speed + L.phase + scroll * 0.0016) +
            L.amp * 0.5 * Math.sin(x / L.wl2 - t * L.speed * 0.7 + scroll * 0.0009);
          if (x === -20) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }

        const grad = ctx.createLinearGradient(0, 0, w, 0);
        grad.addColorStop(0, `rgba(${L.color},0)`);
        grad.addColorStop(0.5, `rgba(${L.color},${L.alpha})`);
        grad.addColorStop(1, `rgba(${L.color},0)`);
        ctx.strokeStyle = grad;
        ctx.lineWidth = L.width;
        ctx.shadowColor = `rgba(${L.color},${L.alpha})`;
        ctx.shadowBlur = 14;
        ctx.stroke();
      }

      // erase the field out of the top band so it never sits behind the header/headings
      ctx.shadowBlur = 0;
      ctx.globalCompositeOperation = "destination-out";
      const fade = ctx.createLinearGradient(0, 0, 0, h);
      fade.addColorStop(0, "rgba(0,0,0,0.92)");
      fade.addColorStop(0.22, "rgba(0,0,0,0)");
      ctx.fillStyle = fade;
      ctx.fillRect(0, 0, w, h * 0.3);

      ctx.globalCompositeOperation = "source-over";

      if (!reduceMotion) raf = requestAnimationFrame(render);
    };

    raf = requestAnimationFrame(render);

    let onScroll: (() => void) | null = null;
    if (reduceMotion) {
      const target: EventTarget = scroller ?? window;
      onScroll = () => {
        cancelAnimationFrame(raf);
        raf = requestAnimationFrame(render);
      };
      target.addEventListener("scroll", onScroll, { passive: true });
      return () => {
        cancelAnimationFrame(raf);
        ro.disconnect();
        target.removeEventListener("scroll", onScroll as EventListener);
      };
    }

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [scrollTargetId]);

  return <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden="true" />;
}

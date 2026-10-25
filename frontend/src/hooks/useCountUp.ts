import { useEffect, useRef, useState } from "react";

// Tweens a displayed number from its previous value to a new target over durationMs whenever
// the target changes (including the first time it arrives from null) - a plain RAF loop, no
// animation library. Used for headline figures that should feel "live" rather than snapping.
export function useCountUp(target: number | null, durationMs = 800): number | null {
  const [displayed, setDisplayed] = useState<number | null>(target);
  const fromRef = useRef<number | null>(target);

  useEffect(() => {
    if (target === null) {
      setDisplayed(null);
      fromRef.current = null;
      return;
    }
    const targetValue: number = target;
    const from = fromRef.current ?? targetValue;
    const start = performance.now();
    let frame: number;

    function tick(now: number) {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplayed(from + (targetValue - from) * eased);
      if (t < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        fromRef.current = targetValue;
      }
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, durationMs]);

  return displayed;
}

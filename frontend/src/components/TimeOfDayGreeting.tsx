import { useEffect, useState } from "react";

// A single, honestly-scoped nod to PCC's pc-art-tod-* (time-of-day) illustration family -
// NOT an attempt at their real system, which is hundreds of hand-animated scene classes
// across many themed illustration sets (calendar, capture, craft, data-governance, depth...).
// This is one small inline SVG that shifts between 4 time-of-day states on the viewer's own
// clock, animated with the same --dur-*/--ease-* tokens the rest of the app now uses.

type TimeOfDay = "dawn" | "day" | "dusk" | "night";

function timeOfDay(hour: number): TimeOfDay {
  if (hour >= 5 && hour < 8) return "dawn";
  if (hour >= 8 && hour < 17) return "day";
  if (hour >= 17 && hour < 20) return "dusk";
  return "night";
}

const PALETTE: Record<TimeOfDay, { sky: string; body: string; glow: string }> = {
  dawn: { sky: "#f5c493", body: "#f2994a", glow: "rgba(242,153,74,.35)" },
  day: { sky: "#9fd4ea", body: "#fdd835", glow: "rgba(253,216,53,.35)" },
  dusk: { sky: "#7b6a9e", body: "#e96f23", glow: "rgba(233,111,35,.35)" },
  night: { sky: "#1b1b3a", body: "#e7c663", glow: "rgba(231,198,99,.3)" },
};

export function TimeOfDayGreeting() {
  const [tod, setTod] = useState<TimeOfDay>(() => timeOfDay(new Date().getHours()));

  useEffect(() => {
    const id = setInterval(() => setTod(timeOfDay(new Date().getHours())), 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  const { sky, body, glow } = PALETTE[tod];
  const isNight = tod === "night";

  return (
    <div
      title={`Good ${tod === "day" ? "afternoon" : tod}`}
      style={{
        width: 36,
        height: 36,
        borderRadius: "50%",
        background: sky,
        position: "relative",
        overflow: "hidden",
        transition: `background var(--dur-modal) var(--ease-standard)`,
        flexShrink: 0,
      }}
    >
      <style>{`
        @keyframes tod-glow { 0%, 100% { opacity: .55; } 50% { opacity: 1; } }
        @keyframes tod-twinkle { 0%, 100% { opacity: .3; } 50% { opacity: .9; } }
      `}</style>
      <div
        style={{
          position: "absolute",
          width: 16,
          height: 16,
          borderRadius: "50%",
          background: body,
          top: tod === "day" ? 10 : 8,
          left: tod === "dawn" ? 10 : tod === "dusk" ? 20 : 14,
          boxShadow: `0 0 10px 3px ${glow}`,
          animation: `tod-glow var(--dur-kpi) var(--ease-standard) infinite`,
          transition: `top var(--dur-modal) var(--ease-standard), left var(--dur-modal) var(--ease-standard)`,
        }}
      />
      {isNight &&
        [{ x: 6, y: 8, d: 0 }, { x: 28, y: 12, d: 400 }, { x: 10, y: 24, d: 800 }].map((star, i) => (
          <div
            key={i}
            style={{
              position: "absolute",
              width: 2,
              height: 2,
              borderRadius: "50%",
              background: "#ffffff",
              top: star.y,
              left: star.x,
              animation: `tod-twinkle 2.4s ease-in-out ${star.d}ms infinite`,
            }}
          />
        ))}
    </div>
  );
}

/**
 * The Mosaic tab bar, as data.
 *
 * This lives outside MosaicShell because two different consumers need it: the shell renders
 * it as navigation, and GenieAskPanel reads it to name the page a question was asked from.
 * Importing it from the shell would make the shell and the panel import each other - legal,
 * but it puts TABS in the temporal dead zone during module evaluation, which is a trap to
 * leave lying around for whoever next needs the route list.
 */
/**
 * Thirteen tabs became four surfaces, because thirteen tabs is not thirteen answers - it is
 * one answer thirteen times, each cut a different way, none of them composing. A question
 * that spanned two tabs meant reading across two tabs and doing the arithmetic yourself.
 *
 *   Command    the value chain: what we deployed, what ran through it, what came back
 *   Explore    the cube: Solution x Metric x Entity x Time, every cell drillable
 *   Entity 360 one practice or one radiologist, everything we know, on a real URL
 *   Cockpit    the operator's day: worklist, MVP, baseline decisions
 *
 * Capture is the fifth tab and is not a surface. It stays because no capture measure is in
 * the cube yet, so Explore cannot answer its question - the same rule that keeps Efficiency,
 * Capacity, Shift Utilization, Roster, Scorecard and Pulse routed but off the bar. Every one
 * of those is reachable from the surface that will eventually absorb it. The URLs the four
 * surfaces genuinely do absorb redirect rather than 404; they are in Teams messages and
 * email threads.
 *
 * When the Capacity and Deployment waves land in the cube, Capture leaves this list too.
 */
export const TABS = [
  { to: "/", label: "Command", end: true },
  { to: "/explore", label: "Explore" },
  { to: "/entity", label: "Entity 360" },
  { to: "/cockpit", label: "Cockpit" },
  { to: "/capture", label: "Capture" },
];

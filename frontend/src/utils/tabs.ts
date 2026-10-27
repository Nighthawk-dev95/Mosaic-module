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
 * Explore replaces five tabs that each answered one fixed question - Volume, Efficiency,
 * Capacity, Non-Drafted and Shift Utilization. None of them composed, so a question spanning
 * two of them meant reading across two tabs. Their routes still resolve; App.tsx redirects
 * them, because these URLs are in Teams messages and email threads.
 */
export const TABS = [
  { to: "/", label: "Today", end: true },
  { to: "/explore", label: "Explore" },
  { to: "/mvp", label: "MVP" },
  { to: "/baseline-review", label: "Baseline Review" },
  { to: "/radiologist-lookup", label: "Radiologist Lookup" },
  { to: "/capture", label: "Capture" },
  { to: "/scorecard", label: "Rad Mosaic Scorecard" },
  { to: "/roster", label: "Roster" },
  { to: "/pulse", label: "Mosaic Pulse" },
];

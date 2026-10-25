/**
 * The Mosaic tab bar, as data.
 *
 * This lives outside MosaicShell because two different consumers need it: the shell renders
 * it as navigation, and GenieAskPanel reads it to name the page a question was asked from.
 * Importing it from the shell would make the shell and the panel import each other - legal,
 * but it puts TABS in the temporal dead zone during module evaluation, which is a trap to
 * leave lying around for whoever next needs the route list.
 */
export const TABS = [
  { to: "/", label: "Today", end: true },
  { to: "/mvp", label: "MVP" },
  { to: "/volume", label: "Volume" },
  { to: "/efficiency", label: "Efficiency" },
  { to: "/capacity", label: "Capacity" },
  { to: "/baseline-review", label: "Baseline Review" },
  { to: "/radiologist-lookup", label: "Radiologist Lookup" },
  { to: "/capture", label: "Capture" },
  { to: "/scorecard", label: "Rad Mosaic Scorecard" },
  { to: "/roster", label: "Roster" },
  { to: "/non-drafted", label: "Non-Drafted" },
  { to: "/pulse", label: "Mosaic Pulse" },
  { to: "/shift-utilization", label: "Shift Utilization" },
];

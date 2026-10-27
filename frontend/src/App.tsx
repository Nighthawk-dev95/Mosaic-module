import { Routes, Route, Navigate } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { MosaicShell } from "./components/MosaicShell";
import { FilterProvider } from "./context/FilterContext";
import { ThemeProvider } from "./context/ThemeContext";
import { MosaicIntelligence } from "./pages/MosaicIntelligence";
import { Mvp } from "./pages/Mvp";
import { RadiologistRoster } from "./pages/RadiologistRoster";
import { EfficiencyDetail } from "./pages/EfficiencyDetail";
import { VolumeDetail } from "./pages/VolumeDetail";
import { CapacityDetail } from "./pages/CapacityDetail";
import { BaselineReviewQueue } from "./pages/BaselineReviewQueue";
import { RadiologistLookup } from "./pages/RadiologistLookup";
import { NonDraftedDetail } from "./pages/NonDraftedDetail";
import { CaptureDetail } from "./pages/CaptureDetail";
import { RadMosaicScorecard } from "./pages/RadMosaicScorecard";
import { DraftVsFinal } from "./pages/DraftVsFinal";
import { MosaicPulse } from "./pages/MosaicPulse";
import { ShiftUtilization } from "./pages/ShiftUtilization";
import { Explorer } from "./pages/Explorer";

export default function App() {
  return (
    <ThemeProvider>
      <FilterProvider>
        <div style={{ display: "flex", height: "100vh" }}>
          <Sidebar />
          <Routes>
            <Route element={<MosaicShell />}>
              <Route path="/" element={<MosaicIntelligence />} />
              <Route path="/mvp" element={<Mvp />} />
              <Route path="/roster" element={<RadiologistRoster />} />
              <Route path="/explore" element={<Explorer />} />
              {/*
                Volume is the one page the cube fully supersedes today - all seven stored
                measures are its own. It redirects rather than 404s because these URLs are in
                Teams messages and email threads. The other four pages Explore will eventually
                absorb stay routed and reachable from Explore itself: their metrics are not in
                the cube yet, so redirecting them now would delete working answers.
              */}
              <Route path="/volume" element={<Navigate to="/explore" replace />} />
              <Route path="/volume-detail" element={<VolumeDetail />} />
              <Route path="/efficiency" element={<EfficiencyDetail />} />
              <Route path="/capacity" element={<CapacityDetail />} />
              <Route path="/baseline-review" element={<BaselineReviewQueue />} />
              <Route path="/radiologist-lookup" element={<RadiologistLookup />} />
              <Route path="/non-drafted" element={<NonDraftedDetail />} />
              <Route path="/capture" element={<CaptureDetail />} />
              <Route path="/scorecard" element={<RadMosaicScorecard />} />
              <Route path="/draft-vs-final" element={<DraftVsFinal />} />
              <Route path="/pulse" element={<MosaicPulse />} />
              <Route path="/shift-utilization" element={<ShiftUtilization />} />
            </Route>
          </Routes>
        </div>
      </FilterProvider>
    </ThemeProvider>
  );
}

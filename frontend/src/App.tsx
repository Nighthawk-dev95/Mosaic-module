import { Routes, Route } from "react-router-dom";
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
              <Route path="/volume" element={<VolumeDetail />} />
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

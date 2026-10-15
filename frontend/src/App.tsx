import { Routes, Route } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { MosaicShell } from "./components/MosaicShell";
import { FilterProvider } from "./context/FilterContext";
import { ThemeProvider } from "./context/ThemeContext";
import { MosaicIntelligence } from "./pages/MosaicIntelligence";
import { RadiologistRoster } from "./pages/RadiologistRoster";
import { DeploymentDetail } from "./pages/DeploymentDetail";
import { EfficiencyDetail } from "./pages/EfficiencyDetail";
import { CapacityDetail } from "./pages/CapacityDetail";
import { BaselineReviewQueue } from "./pages/BaselineReviewQueue";
import { ExternalFeedback } from "./pages/ExternalFeedback";
import { AdoptionMap } from "./pages/AdoptionMap";
import { Reconciliation } from "./pages/Reconciliation";
import { NonDraftedDetail } from "./pages/NonDraftedDetail";
import { CaptureDetail } from "./pages/CaptureDetail";
import { ScorecardDetail } from "./pages/ScorecardDetail";
import { DraftVsFinal } from "./pages/DraftVsFinal";

export default function App() {
  return (
    <ThemeProvider>
      <FilterProvider>
        <div style={{ display: "flex", height: "100vh" }}>
          <Sidebar />
          <Routes>
            <Route element={<MosaicShell />}>
              <Route path="/" element={<MosaicIntelligence />} />
              <Route path="/roster" element={<RadiologistRoster />} />
              <Route path="/deployment" element={<DeploymentDetail />} />
              <Route path="/efficiency" element={<EfficiencyDetail />} />
              <Route path="/capacity" element={<CapacityDetail />} />
              <Route path="/baseline-review" element={<BaselineReviewQueue />} />
              <Route path="/external-feedback" element={<ExternalFeedback />} />
              <Route path="/adoption-map" element={<AdoptionMap />} />
              <Route path="/reconciliation" element={<Reconciliation />} />
              <Route path="/non-drafted" element={<NonDraftedDetail />} />
              <Route path="/capture" element={<CaptureDetail />} />
              <Route path="/scorecard" element={<ScorecardDetail />} />
              <Route path="/draft-vs-final" element={<DraftVsFinal />} />
            </Route>
          </Routes>
        </div>
      </FilterProvider>
    </ThemeProvider>
  );
}

import { Routes, Route } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { FilterProvider } from "./context/FilterContext";
import { MosaicIntelligence } from "./pages/MosaicIntelligence";
import { RadiologistRoster } from "./pages/RadiologistRoster";
import { DeploymentDetail } from "./pages/DeploymentDetail";
import { EfficiencyDetail } from "./pages/EfficiencyDetail";
import { CapacityDetail } from "./pages/CapacityDetail";
import { NonDraftedDetail } from "./pages/NonDraftedDetail";
import { CaptureDetail } from "./pages/CaptureDetail";
import { ScorecardDetail } from "./pages/ScorecardDetail";

export default function App() {
  return (
    <FilterProvider>
      <div style={{ display: "flex", height: "100vh" }}>
        <Sidebar />
        <Routes>
          <Route path="/" element={<MosaicIntelligence />} />
          <Route path="/roster" element={<RadiologistRoster />} />
          <Route path="/deployment" element={<DeploymentDetail />} />
          <Route path="/efficiency" element={<EfficiencyDetail />} />
          <Route path="/capacity" element={<CapacityDetail />} />
          <Route path="/non-drafted" element={<NonDraftedDetail />} />
          <Route path="/capture" element={<CaptureDetail />} />
          <Route path="/scorecard" element={<ScorecardDetail />} />
        </Routes>
      </div>
    </FilterProvider>
  );
}

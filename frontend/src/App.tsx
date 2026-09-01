import { Routes, Route } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { FilterProvider } from "./context/FilterContext";
import { MosaicIntelligence } from "./pages/MosaicIntelligence";
import { RadiologistRoster } from "./pages/RadiologistRoster";
import { DeploymentDetail } from "./pages/DeploymentDetail";
import { EfficiencyDetail } from "./pages/EfficiencyDetail";
import { CapacityDetail } from "./pages/CapacityDetail";

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
        </Routes>
      </div>
    </FilterProvider>
  );
}

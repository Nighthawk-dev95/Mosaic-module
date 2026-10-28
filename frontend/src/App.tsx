import { Routes, Route, Navigate } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { MosaicShell } from "./components/MosaicShell";
import { FilterProvider } from "./context/FilterContext";
import { ThemeProvider } from "./context/ThemeContext";
import { MosaicIntelligence } from "./pages/MosaicIntelligence";
import { RadiologistRoster } from "./pages/RadiologistRoster";
import { EfficiencyDetail } from "./pages/EfficiencyDetail";
import { VolumeDetail } from "./pages/VolumeDetail";
import { CapacityDetail } from "./pages/CapacityDetail";
import { NonDraftedDetail } from "./pages/NonDraftedDetail";
import { CaptureDetail } from "./pages/CaptureDetail";
import { RadMosaicScorecard } from "./pages/RadMosaicScorecard";
import { DraftVsFinal } from "./pages/DraftVsFinal";
import { MosaicPulse } from "./pages/MosaicPulse";
import { ShiftUtilization } from "./pages/ShiftUtilization";
import { Explorer } from "./pages/Explorer";
import { Command } from "./pages/Command";
import { Cockpit } from "./pages/Cockpit";
import { Entity360, EntityFinder } from "./pages/Entity360";

export default function App() {
  return (
    <ThemeProvider>
      <FilterProvider>
        <div style={{ display: "flex", height: "100vh" }}>
          <Sidebar />
          <Routes>
            <Route element={<MosaicShell />}>
              {/*
                Four surfaces. Command is the value chain, Explore is the cube, Entity 360 is
                one practice or one radiologist, Cockpit is the operator's day.
              */}
              <Route path="/" element={<Command />} />
              <Route path="/explore" element={<Explorer />} />
              <Route path="/entity" element={<EntityFinder />} />
              <Route path="/entity/:type/:id" element={<Entity360 />} />
              <Route path="/cockpit" element={<Cockpit />} />
              <Route path="/capture" element={<CaptureDetail />} />

              {/*
                Two kinds of retirement, and the difference matters.

                REDIRECTS, for pages whose every answer now lives somewhere else. These URLs
                are in Teams messages and email threads, so they resolve rather than 404.
              */}
              <Route path="/volume" element={<Navigate to="/explore" replace />} />
              <Route path="/mvp" element={<Navigate to="/cockpit" replace />} />
              <Route path="/baseline-review" element={<Navigate to="/cockpit" replace />} />
              <Route path="/radiologist-lookup" element={<Navigate to="/entity" replace />} />

              {/*
                STILL ROUTED, off the tab bar, linked from the surface that will eventually
                absorb them. Each one answers something the four surfaces do not yet: the
                cube has no capacity, efficiency or capture measures, the roster is the only
                browsable radiologist index, and Pulse carries the 810-respondent rad survey.
                Redirecting these would delete working answers, which is a different act from
                moving them.
              */}
              <Route path="/intelligence" element={<MosaicIntelligence />} />
              <Route path="/pulse" element={<MosaicPulse />} />
              <Route path="/roster" element={<RadiologistRoster />} />
              <Route path="/scorecard" element={<RadMosaicScorecard />} />
              <Route path="/volume-detail" element={<VolumeDetail />} />
              <Route path="/efficiency" element={<EfficiencyDetail />} />
              <Route path="/capacity" element={<CapacityDetail />} />
              <Route path="/non-drafted" element={<NonDraftedDetail />} />
              <Route path="/draft-vs-final" element={<DraftVsFinal />} />
              <Route path="/shift-utilization" element={<ShiftUtilization />} />

              {/* Anything else lands on the value chain rather than a blank frame. */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </div>
      </FilterProvider>
    </ThemeProvider>
  );
}

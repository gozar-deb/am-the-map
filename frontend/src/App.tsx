import { useEffect } from "react";
import TopBar from "./components/TopBar";
import SensorPanel from "./components/SensorPanel";
import EnvironmentPanel from "./components/EnvironmentPanel";
import TabBar from "./components/TabBar";
import Scene from "./three/Scene";
import SceneControls from "./components/SceneControls";
import CSIStream from "./components/CSIStream";
import OccupancyPanel from "./components/OccupancyPanel";
import TrackingPanel from "./components/TrackingPanel";
import HeatmapPanel from "./components/HeatmapPanel";
import TimelinePanel from "./components/TimelinePanel";
import { useAppStore } from "./state/store";

export default function App() {
  const activeTab = useAppStore((s) => s.activeTab);
  const connect = useAppStore((s) => s.connect);

  useEffect(() => {
    connect();
  }, [connect]);

  return (
    <div className="flex h-screen flex-col">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <SensorPanel />
        <main className="relative min-w-0 flex-1 bg-void">
          {activeTab === "map" && (
            <>
              <Scene />
              <SceneControls />
            </>
          )}
          {activeTab === "signal" && <CSIStream />}
          {activeTab === "occupancy" && <OccupancyPanel />}
          {activeTab === "tracking" && <TrackingPanel />}
          {activeTab === "heatmap" && <HeatmapPanel />}
          {activeTab === "timeline" && <TimelinePanel />}
        </main>
        <EnvironmentPanel />
      </div>
      <TabBar />
    </div>
  );
}

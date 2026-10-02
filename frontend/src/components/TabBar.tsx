import { useAppStore } from "../state/store";
import type { TabKey } from "../types";

const TABS: [TabKey, string][] = [
  ["signal", "Signal"],
  ["map", "Map"],
  ["occupancy", "Occupancy"],
  ["tracking", "Tracking"],
  ["heatmap", "Heatmap"],
  ["timeline", "Timeline"],
];

export default function TabBar() {
  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);

  return (
    <nav className="flex h-10 shrink-0 border-t border-hairline bg-panel">
      {TABS.map(([key, label]) => (
        <button
          key={key}
          onClick={() => setActiveTab(key)}
          className={`flex-1 border-r border-hairline font-mono text-xs uppercase tracking-wider transition-colors ${
            activeTab === key ? "bg-panel2 text-signal" : "text-muted hover:text-ink"
          }`}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}

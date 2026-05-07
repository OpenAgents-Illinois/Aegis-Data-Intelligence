import { useState, useCallback } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import SplashScreen from "./components/SplashScreen";
import Landing from "./pages/Landing";
import Overview from "./pages/Overview";
import IncidentDetail from "./pages/IncidentDetail";
import LineageExplorer from "./pages/LineageExplorer";
import Settings from "./pages/Settings";

// Root application component. Two modes:
// 1. Landing page (/) — standalone marketing page, no sidebar
// 2. Dashboard (/dashboard, /incidents/:id, /lineage, /settings) —
//    shown inside Layout (sidebar + top bar) after a splash screen animation
export default function App() {
  const location = useLocation();
  const isLanding = location.pathname === "/";

  // Splash screen plays a 2.8-second shield animation on first dashboard load.
  // dashboardReady controls opacity — the dashboard is invisible (opacity-0)
  // until the splash finishes to prevent layout flash.
  const [showSplash, setShowSplash] = useState(!isLanding);
  const [dashboardReady, setDashboardReady] = useState(isLanding);

  const handleSplashComplete = useCallback(() => {
    setShowSplash(false);
    // Small delay so the exit animation finishes before content fades in
    setTimeout(() => setDashboardReady(true), 50);
  }, []);

  // Landing page is standalone — no sidebar layout, no splash
  if (isLanding) {
    return <Landing />;
  }

  return (
    <>
      {/* Animated splash overlay — auto-dismisses after 2.8s */}
      {showSplash && <SplashScreen onComplete={handleSplashComplete} />}

      {/* Dashboard content — hidden until splash completes */}
      <div className={dashboardReady ? "animate-dashboard-enter" : "opacity-0"}>
        <Layout>
          <Routes>
            <Route path="/dashboard" element={<Overview />} />
            <Route path="/incidents/:id" element={<IncidentDetail />} />
            <Route path="/lineage" element={<LineageExplorer />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Layout>
      </div>
    </>
  );
}

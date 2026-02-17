import { useState, useCallback } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import SplashScreen from "./components/SplashScreen";
import Landing from "./pages/Landing";
import Overview from "./pages/Overview";
import IncidentDetail from "./pages/IncidentDetail";
import LineageExplorer from "./pages/LineageExplorer";
import Settings from "./pages/Settings";

export default function App() {
  const location = useLocation();
  const isLanding = location.pathname === "/";

  const [showSplash, setShowSplash] = useState(!isLanding);
  const [dashboardReady, setDashboardReady] = useState(isLanding);

  const handleSplashComplete = useCallback(() => {
    setShowSplash(false);
    setTimeout(() => setDashboardReady(true), 50);
  }, []);

  // Landing page is standalone — no sidebar layout, no splash
  if (isLanding) {
    return <Landing />;
  }

  return (
    <>
      {showSplash && <SplashScreen onComplete={handleSplashComplete} />}

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

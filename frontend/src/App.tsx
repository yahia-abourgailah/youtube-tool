import React, { useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom';
import { LayoutDashboard, Users, Video, Music, Settings, Download, BarChart2, Mic, Menu, X, Scissors } from 'lucide-react';
import './index.css';

// Lazy load pages
const Dashboard = React.lazy(() => import('./pages/Dashboard'));
const Channels = React.lazy(() => import('./pages/Channels'));
const Videos = React.lazy(() => import('./pages/Videos'));
const Chunks = React.lazy(() => import('./pages/Chunks'));
const Export = React.lazy(() => import('./pages/Export'));
const Transcription = React.lazy(() => import('./pages/Transcription'));
const SettingsPage = React.lazy(() => import('./pages/Settings'));
const Statistics = React.lazy(() => import('./pages/Statistics'));
const Trimming = React.lazy(() => import('./pages/Trimming'));

const Sidebar = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
  const location = useLocation();

  // Close sidebar on navigation (mobile)
  const handleNav = useCallback(() => {
    onClose();
  }, [onClose]);

  // Re-check on every route change to auto-close
  React.useEffect(() => {
    onClose();
  }, [location.pathname, onClose]);

  return (
    <>
      <div className={`sidebar-overlay ${open ? 'open' : ''}`} onClick={onClose} />
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div style={{ marginBottom: '2rem', padding: '0 1rem' }}>
          <h1 style={{ fontSize: '1.2rem', fontWeight: 'bold', color: 'var(--accent-primary)' }}>YouTube Data Generator</h1>
        </div>
        <nav>
          <NavLink to="/" onClick={handleNav} className={({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`}>
            <LayoutDashboard size={20} /> Dashboard
          </NavLink>
          <NavLink to="/channels" onClick={handleNav} className={({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Users size={20} /> Channels
          </NavLink>
          <NavLink to="/videos" onClick={handleNav} className={({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Video size={20} /> Videos
          </NavLink>
          <NavLink to="/chunks" onClick={handleNav} className={({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Music size={20} /> Chunks
          </NavLink>
          <NavLink to="/trim" onClick={handleNav} className={({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Scissors size={20} /> Trimming
          </NavLink>
          <NavLink to="/transcribe" onClick={handleNav} className={({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Mic size={20} /> Transcription
          </NavLink>
          <NavLink to="/export" onClick={handleNav} className={({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Download size={20} /> Export
          </NavLink>
          <NavLink to="/stats" onClick={handleNav} className={({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`}>
            <BarChart2 size={20} /> Stats
          </NavLink>
          <NavLink to="/settings" onClick={handleNav} className={({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Settings size={20} /> Settings
          </NavLink>
        </nav>
      </aside>
    </>
  );
};

const App = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <Router>
      <div className="app-container">
        <button className="sidebar-toggle" onClick={() => setSidebarOpen(o => !o)}>
          {sidebarOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <main className="main-content">
          <React.Suspense fallback={<div style={{ padding: '2rem' }}>Loading...</div>}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/channels" element={<Channels />} />
              <Route path="/videos" element={<Videos />} />
              <Route path="/chunks" element={<Chunks />} />
              <Route path="/trim" element={<Trimming />} />
              <Route path="/transcribe" element={<Transcription />} />
              <Route path="/export" element={<Export />} />
              <Route path="/stats" element={<Statistics />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </React.Suspense>
        </main>
      </div>
    </Router>
  );
};

export default App;

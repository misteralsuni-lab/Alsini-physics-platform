import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, Outlet } from 'react-router-dom';
import { supabase } from './lib/supabaseClient';
import Navbar from './components/Navbar';
import NoiseOverlay from './components/NoiseOverlay';
import Hero from './components/Hero';
import Features from './components/Features';
import Philosophy from './components/Philosophy';
import Protocol from './components/Protocol';
import CTA from './components/CTA';
import Footer from './components/Footer';
import Auth from './components/Auth';
import UpdatePassword from './components/UpdatePassword';
import VLEDashboard, { DashboardHome } from './components/VLEDashboard';
import InteractiveTutor from './components/InteractiveTutor';

const Home = () => (
  <>
    <Hero />
    <Features />
    <Philosophy />
    <Protocol />
    <CTA />
  </>
);
const AppContent = ({ session, activeTab, setActiveTab }) => {
  const location = useLocation();
  const isAuthPage = location.pathname === '/auth' || location.pathname === '/update-password';
  const isDashboard = location.pathname.startsWith('/dashboard');
  const hideGlobalNavAndFooter = isAuthPage || isDashboard;

  return (
    <main className="relative min-h-screen bg-[#050505] selection:bg-accent-purple/30 selection:text-white">
      <NoiseOverlay />
      {!hideGlobalNavAndFooter && <Navbar session={session} />}
      <Routes>
        <Route path="/" element={session ? <Navigate to="/dashboard" replace /> : <Home />} />
        <Route 
          path="/auth" 
          element={session ? <Navigate to="/dashboard" replace /> : <Auth />} 
        />
        <Route path="/update-password" element={<UpdatePassword />} />
        <Route 
          path="/dashboard" 
          element={session ? <VLEDashboard session={session} /> : <Navigate to="/auth" replace />}
        >
          <Route index element={<DashboardHome />} />
          <Route 
            path="unit/:unitId/chapter/:chapterId" 
            element={<InteractiveTutor activeTab={activeTab} setActiveTab={setActiveTab} />} 
          />
        </Route>
      </Routes>
      {!hideGlobalNavAndFooter && <Footer />}
    </main>
  );
};

function App() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('Lesson');

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  if (loading) {
    // Avoid the initial null-session redirect-to-/auth that would drop a
    // deep link (e.g. /dashboard/unit/.../chapter/...). Wait until the
    // persisted session has been restored before routing.
    return <div className="min-h-screen bg-[#050505]" />;
  }

  return (
    <Router>
      <AppContent session={session} activeTab={activeTab} setActiveTab={setActiveTab} />
    </Router>
  );
}

export default App;

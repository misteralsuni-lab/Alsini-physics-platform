import React, { useEffect, useState, Component } from 'react';
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

// Error Boundary — catches render crashes so the page doesn't go blank.
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary] Caught:', error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#050505] flex items-center justify-center p-8">
          <div className="max-w-md w-full bg-[#0A0A0A] border border-red-500/20 rounded-2xl p-8 text-center">
            <h2 className="text-xl font-medium text-red-400 mb-3">Something went wrong</h2>
            <p className="text-gray-500 text-sm mb-6">
              The page encountered an error. Reloading usually fixes it.
            </p>
            <button
              onClick={this.handleReload}
              className="px-6 py-2.5 rounded-xl bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-all"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

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
          element={session ? <VLEDashboard /> : <Navigate to="/auth" replace />}
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
  const [activeTab, setActiveTab] = useState('Worksheet');

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
    <ErrorBoundary>
      <Router>
        <AppContent session={session} activeTab={activeTab} setActiveTab={setActiveTab} />
      </Router>
    </ErrorBoundary>
  );
}

export default App;

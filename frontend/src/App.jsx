import React, { useEffect, useState, Component } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
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
import VLEDashboard from './components/VLEDashboard';

// Error Boundary — catches render crashes so the page doesn't go blank
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
const AppContent = ({ session }) => {
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
          path="/dashboard/*" 
          element={session ? <VLEDashboard session={session} /> : <Navigate to="/auth" replace />} 
        />
      </Routes>
      {!hideGlobalNavAndFooter && <Footer />}
    </main>
  );
};

function App() {
  const [session, setSession] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    // Get initial session — once resolved, clear loading state
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setAuthLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      // Don't set authLoading=false here — only the initial getSession should clear it.
      // This prevents flicker redirects during token refresh.
    });

    return () => subscription.unsubscribe();
  }, []);

  // While the initial session check is in progress, show a loading screen
  // instead of redirecting to /auth (which causes the "disappearing dashboard")
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin"></div>
          <p className="text-gray-500 text-sm font-light">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <Router>
        <AppContent session={session} />
      </Router>
    </ErrorBoundary>
  );
}

export default App;

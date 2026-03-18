import React, { useEffect, useState } from 'react';
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

  return (
    <main className="relative min-h-screen bg-background selection:bg-accent-purple/30 selection:text-white">
      <NoiseOverlay />
      {!isAuthPage && <Navbar session={session} />}
      <Routes>
        <Route path="/" element={<Home />} />
        <Route 
          path="/auth" 
          element={session ? <Navigate to="/" replace /> : <Auth />} 
        />
        <Route path="/update-password" element={<UpdatePassword />} />
      </Routes>
      {!isAuthPage && <Footer />}
    </main>
  );
};

function App() {
  const [session, setSession] = useState(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  return (
    <Router>
      <AppContent session={session} />
    </Router>
  );
}

export default App;

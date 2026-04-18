import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Sidebar from './Sidebar';
import InteractiveTutor from './InteractiveTutor';

const DashboardHome = () => (
  <div className="p-8 max-w-4xl mx-auto w-full">
    <div className="bg-[#0A0A0A]/50 border border-white/5 rounded-2xl p-8 backdrop-blur-sm">
      <h1 className="text-4xl font-drama text-white mb-4">Welcome to your Dashboard</h1>
      <p className="text-gray-300 text-lg">Select a unit from the sidebar to begin your revision journey.</p>
    </div>
  </div>
);



const VLEDashboard = ({ session }) => {
  return (
    <div className="h-screen w-full flex bg-[#050505] overflow-hidden relative">
      {/* 
         No Top Navbar needed, Sidebar acts as the main app nav 
         Noise Overlay for premium aesthetic 
      */}
      <div 
         className="absolute inset-0 z-0 pointer-events-none opacity-[0.03]"
         style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noiseFilter\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.65\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noiseFilter)\'/%3E%3C/svg%3E")' }}
      ></div>

      {/* Sidebar: Flex child fixed to left */}
      <Sidebar />
      
      {/* Scrollable Main Content Pane */}
      <main className="flex-1 overflow-hidden relative z-10 flex flex-col">
        {/* We can place the top-right user controls here later if needed, but for now just the content */}
        <div className="flex-1 h-full overflow-y-auto styled-scrollbar">
           <Routes>
             <Route path="/" element={<div className="py-8 min-h-full"><DashboardHome /></div>} />
             <Route path="/unit/:unitId/chapter/:chapterId" element={<InteractiveTutor />} />
           </Routes>
        </div>
      </main>
    </div>
  );
};

export default VLEDashboard;

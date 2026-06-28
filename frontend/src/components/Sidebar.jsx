import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { supabase } from '../lib/supabaseClient';
import { ChevronDown, ChevronRight, BookOpen, FlaskConical, Loader2, LogOut, Menu, ChevronLeft } from 'lucide-react';

const Sidebar = () => {
  const [units, setUnits] = useState([]);
  const [chapters, setChapters] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedUnits, setExpandedUnits] = useState({});
  const [isPhysicsOnly, setIsPhysicsOnly] = useState(true);
  const [isOpen, setIsOpen] = useState(true);

  useEffect(() => {
    fetchSyllabusData();
  }, []);

  const fetchSyllabusData = async () => {
    setIsLoading(true);
    try {
      // Fetch units
      const { data: unitsData, error: unitsError } = await supabase
        .from('units')
        .select('*')
        .order('created_at', { ascending: true });
        
      if (unitsError) throw unitsError;

      // Fetch chapters with their specification points
      const { data: chaptersData, error: chaptersError } = await supabase
        .from('chapters')
        .select(`
          *,
          specification_points (
            id,
            reference_code,
            description,
            is_physics_only
          )
        `)
        .order('created_at', { ascending: true });

      if (chaptersError) throw chaptersError;

      setUnits(unitsData);
      setChapters(chaptersData);
      
      // Initialize first unit as expanded
      if (unitsData.length > 0) {
        setExpandedUnits({ [unitsData[0].id]: true });
      }
    } catch (error) {
      console.error('Error fetching syllabus data:', error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleUnit = (unitId) => {
    setExpandedUnits(prev => ({
      ...prev,
      [unitId]: !prev[unitId]
    }));
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  return (
    <>
      {/* Floating Toggle Button when Sidebar is closed */}
      {!isOpen && (
        <button 
          onClick={() => setIsOpen(true)}
          className="absolute top-6 left-6 z-50 p-2.5 bg-[#0A0A0A] border border-white/10 rounded-xl text-gray-400 hover:text-white transition-all shadow-[0_0_20px_rgba(0,0,0,0.5)] group hover:border-accent-cyan/30"
          aria-label="Open Sidebar"
        >
          <Menu size={20} className="group-hover:scale-110 transition-transform" />
        </button>
      )}

      <aside className={`w-80 flex-shrink-0 border-r border-white/5 bg-[#0A0A0A] flex flex-col h-full z-40 shadow-2xl relative transition-all duration-300 ${isOpen ? 'translate-x-0 ml-0' : '-translate-x-full -ml-80'}`}>
        {/* Brand Header */}
        <div className="p-6 border-b border-white/5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative">
              <div className="absolute inset-0 bg-accent-cyan opacity-20 blur-md rounded-full group-hover:opacity-40 transition-opacity"></div>
              <div className="w-10 h-10 rounded-xl bg-white/5 border border-accent-cyan/30 flex items-center justify-center relative z-10 transition-colors group-hover:border-accent-cyan/60">
                <span className="font-drama text-2xl text-accent-cyan">E</span>
              </div>
            </div>
            <span className="font-sans font-bold text-xl tracking-tight text-white">
              EDU<span className="text-accent-cyan">-VLE</span>
            </span>
          </Link>
          <button 
            onClick={() => setIsOpen(false)}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
            aria-label="Close Sidebar"
          >
            <ChevronLeft size={20} />
          </button>
        </div>

      {/* Sleek Triple Science Toggle */}
      <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
         <div className="flex items-center gap-3 text-gray-300">
            <div className={`p-1.5 rounded-lg transition-colors ${isPhysicsOnly ? 'bg-accent-purple/20 text-accent-purple' : 'bg-white/5 text-gray-500'}`}>
              <FlaskConical size={16} />
            </div>
            <span className="font-medium text-sm">Triple Science</span>
         </div>
         <button 
           onClick={() => setIsPhysicsOnly(!isPhysicsOnly)}
           className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-accent-cyan/50 focus:ring-offset-2 focus:ring-offset-[#0A0A0A] ${isPhysicsOnly ? 'bg-accent-cyan' : 'bg-white/10'}`}
         >
           <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${isPhysicsOnly ? 'translate-x-4' : 'translate-x-1'}`} />
         </button>
      </div>

      {/* Navigation Menu */}
      <div className="flex-1 overflow-y-auto py-4 px-3 styled-scrollbar">
        {isLoading ? (
          <div className="flex flex-col gap-4 p-4">
            <div className="h-10 bg-white/5 rounded-lg animate-pulse w-full"></div>
            <div className="h-10 bg-white/5 rounded-lg animate-pulse w-5/6 ml-auto"></div>
            <div className="h-10 bg-white/5 rounded-lg animate-pulse w-4/6 ml-auto"></div>
            <div className="h-10 bg-white/5 rounded-lg animate-pulse w-full mt-4"></div>
            <div className="flex items-center justify-center pt-8 text-accent-cyan">
                <Loader2 className="animate-spin" size={32} />
            </div>
          </div>
        ) : (
          <nav className="space-y-1">
            {units.map((unit) => {
              const unitChapters = chapters.filter(c => c.unit_id === unit.id);
              const isExpanded = expandedUnits[unit.id];

              return (
                <div key={unit.id} className="mb-2">
                  <button
                    onClick={() => toggleUnit(unit.id)}
                    className="w-full flex items-center justify-between p-3 rounded-lg text-white hover:bg-white/5 transition-colors group"
                  >
                    <div className="flex items-center gap-3">
                       <BookOpen size={18} className="text-gray-400 group-hover:text-accent-cyan transition-colors" />
                       <span className="font-semibold text-sm text-left">{unit.title}</span>
                    </div>
                    {isExpanded ? (
                      <ChevronDown size={18} className="text-gray-400" />
                    ) : (
                      <ChevronRight size={18} className="text-gray-400" />
                    )}
                  </button>

                  {/* Chapters Menu */}
                  {isExpanded && (
                    <div className="mt-1 ml-4 pl-4 border-l border-white/5 space-y-1">
                      {unitChapters.map(chapter => {
                         // Check if this chapter has spec points matching the filter
                         const validSpecPoints = chapter.specification_points?.filter(sp => {
                             if (isPhysicsOnly) return true;
                             return !sp.is_physics_only;
                         }) || [];

                         return (
                           <Link
                             key={chapter.id}
                             to={`/dashboard/unit/${unit.id}/chapter/${chapter.id}`}
                             className="flex items-center justify-between py-2 px-3 rounded-md text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-all"
                             title={chapter.title}
                           >
                             <span className="truncate">{chapter.title}</span>
                             {!isPhysicsOnly && validSpecPoints.length === 0 && chapter.specification_points?.length > 0 && (
                                <span className="text-[10px] ml-2 px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 font-bold tracking-wider" title="Triple Science Only">TS</span>
                             )}
                           </Link>
                         );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </nav>
        )}
      </div>

      {/* User Footer / Logout */}
      <div className="p-4 border-t border-white/5">
         <button 
           onClick={handleLogout}
           className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors group"
         >
            <LogOut size={18} className="group-hover:-translate-x-1 transition-transform" />
            <span className="font-semibold text-sm">Sign Out</span>
         </button>
      </div>
    </aside>
   </>
  );
};

export default Sidebar;

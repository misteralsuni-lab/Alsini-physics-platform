import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabaseClient';
import Button from './Button';
import { LogOut, User, Search } from 'lucide-react';

export default function Navbar({ session }) {
    const [scrolled, setScrolled] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [isSearchExpanded, setIsSearchExpanded] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        const handleScroll = () => {
            setScrolled(window.scrollY > 50);
        };
        window.addEventListener('scroll', handleScroll, { passive: true });
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const handleLogout = async () => {
        await supabase.auth.signOut();
        navigate('/');
    };

    return (
        <header className="fixed top-6 left-0 right-0 z-50 flex justify-center pointer-events-none px-4">
            <nav
                className={`pointer-events-auto flex items-center justify-between px-6 py-3 rounded-full transition-all duration-500 ease-out border ${scrolled
                    ? 'bg-background/60 backdrop-blur-xl border-secondary/20 shadow-lg'
                    : 'bg-transparent border-transparent'
                    }`}
                style={{ width: 'min(100%, 800px)' }}
            >
                <Link to="/" className="font-sans font-bold text-xl tracking-tight text-primary">
                    EDU-VLE<span className="text-accent-cyan">.</span>
                </Link>

                <div className="hidden md:flex items-center gap-8 font-sans text-sm font-medium">
                    <a href="#syllabus" className="text-secondary hover:text-accent-cyan transition-colors hover:-translate-y-[1px] transform duration-300 inline-block">Syllabus</a>
                    <a href="#experience" className="text-secondary hover:text-accent-purple transition-colors hover:-translate-y-[1px] transform duration-300 inline-block">Experience</a>
                    <a href="#methodology" className="text-secondary hover:text-primary transition-colors hover:-translate-y-[1px] transform duration-300 inline-block">Methodology</a>
                </div>

                <div className="flex items-center gap-4">
                    {/* Global Search Bar */}
                    <div className="flex items-center relative z-50">
                        {/* Mobile Toggle Button */}
                        <button 
                            className="md:hidden p-2 text-secondary/70 hover:text-accent-cyan hover:bg-white/[0.05] rounded-full transition-all duration-300"
                            onClick={() => setIsSearchExpanded(prev => !prev)}
                            aria-label="Toggle Search"
                            aria-expanded={isSearchExpanded}
                        >
                            <Search size={18} />
                        </button>

                        {/* Search Input Container */}
                        <div className={`
                            absolute md:relative top-full right-0 mt-3 md:mt-0 
                            md:block transition-all duration-500 ease-out origin-top-right
                            ${isSearchExpanded 
                                ? 'scale-100 opacity-100 translate-y-0 pointer-events-auto' 
                                : 'scale-95 opacity-0 -translate-y-2 pointer-events-none md:scale-100 md:opacity-100 md:translate-y-0 md:pointer-events-auto'}
                        `}>
                            {/* Glassmorphic wrapper for mobile popover, transparent on desktop */}
                            <div className="md:bg-transparent md:backdrop-blur-none md:border-none md:p-0 md:shadow-none bg-[#0a0a0a]/90 backdrop-blur-2xl border border-white/[0.08] p-3 rounded-2xl shadow-2xl">
                                <div className="relative group w-[240px] lg:w-[280px]">
                                    <Search 
                                        size={15} 
                                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary/40 opacity-70 group-focus-within:text-accent-cyan group-focus-within:opacity-100 group-focus-within:drop-shadow-[0_0_8px_rgba(0,255,255,0.6)] transition-all duration-500 z-10" 
                                    />
                                    <input
                                        type="text"
                                        value={searchTerm}
                                        onChange={(e) => setSearchTerm(e.target.value)}
                                        placeholder="Search resources..."
                                        className="
                                            w-full bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] 
                                            text-primary placeholder-secondary/40 text-sm rounded-full 
                                            py-2 pl-10 pr-4 outline-none transition-all duration-500 ease-out
                                            hover:bg-white/[0.05] hover:border-white/[0.1]
                                            focus:bg-white/[0.06] focus:border-accent-cyan/50 
                                            focus:shadow-[0_0_20px_rgba(0,255,255,0.15),_inset_0_0_10px_rgba(0,255,255,0.05)] 
                                            focus:ring-1 focus:ring-accent-cyan/40
                                        "
                                    />
                                </div>
                            </div>
                        </div>
                    </div>

                    {session ? (
                        <div className="flex items-center gap-4">
                            <div className="hidden sm:flex items-center gap-2 text-primary text-sm font-medium">
                                <User size={16} className="text-accent-purple" />
                                <span className="max-w-[100px] truncate">{session.user.email}</span>
                            </div>
                            <button 
                                onClick={handleLogout}
                                className="p-2 text-secondary hover:text-red-400 transition-colors"
                                title="Sign Out"
                            >
                                <LogOut size={20} />
                            </button>
                        </div>
                    ) : (
                        <Link to="/auth">
                            <Button variant="cyan" className="text-sm px-5 py-2 font-bold !text-background">Login</Button>
                        </Link>
                    )}
                </div>
            </nav>
        </header>
    );
}

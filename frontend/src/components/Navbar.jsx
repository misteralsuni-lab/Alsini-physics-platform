import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabaseClient';
import Button from './Button';
import { Search, Bell, User, Menu, X, LogOut } from 'lucide-react';

export default function Navbar({ session }) {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const navigate = useNavigate();

    const handleLogout = async () => {
        await supabase.auth.signOut();
        navigate('/');
    };

    return (
        <header className="fixed top-0 left-0 w-full z-50 bg-[#050505]/70 backdrop-blur-xl border-b border-white/10 transition-all duration-300">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-14">
                    
                    {/* 1. Left Section (Brand) */}
                    <div className="flex-shrink-0 flex items-center">
                        <Link to="/" className="font-sans font-bold text-xl tracking-tight text-primary">
                            EDU-VLE<span className="text-accent-cyan">.</span>
                        </Link>
                    </div>

                    {/* 2. Centre Section (Navigation) */}
                    <nav className="hidden md:flex flex-1 justify-center items-center gap-8 font-sans">
                        <Link to="/dashboard" className="text-[13px] font-medium text-secondary hover:text-accent-cyan transition-colors duration-300">Dashboard</Link>
                        <Link to="/courses" className="text-[13px] font-medium text-secondary hover:text-accent-purple transition-colors duration-300">My Courses</Link>
                        <Link to="/community" className="text-[13px] font-medium text-secondary hover:text-primary transition-colors duration-300">Community</Link>
                        <Link to="/admin" className="text-[13px] font-medium text-secondary hover:text-primary transition-colors duration-300">Admin</Link>
                    </nav>

                    {/* 3. Right Section (Utilities) */}
                    <div className="hidden md:flex items-center gap-5">
                        <button className="text-secondary hover:text-accent-cyan transition-colors" aria-label="Search">
                            <Search size={16} />
                        </button>
                        <button className="text-secondary hover:text-accent-purple transition-colors relative" aria-label="Notifications">
                            <Bell size={16} />
                            <span className="absolute -top-0.5 -right-0.5 w-[6px] h-[6px] bg-accent-cyan rounded-full animate-pulse"></span>
                        </button>
                        
                        {session ? (
                            <div className="flex items-center gap-3">
                                <div className="hidden sm:flex items-center gap-2 text-primary text-xs font-medium pl-2 border-l border-white/10">
                                    <User size={14} className="text-accent-purple" />
                                    <span className="max-w-[100px] truncate">{session.user.email}</span>
                                </div>
                                <button onClick={handleLogout} className="p-1 text-secondary hover:text-red-400 transition-colors" title="Log Out">
                                    <LogOut size={16} />
                                </button>
                            </div>
                        ) : (
                            <div className="pl-2 border-l border-white/10">
                                <Link to="/auth">
                                    <Button variant="cyan" className="text-xs px-4 py-1.5 font-bold !text-background rounded-full">Login</Button>
                                </Link>
                            </div>
                        )}
                    </div>

                    {/* Mobile Menu Button */}
                    <div className="flex md:hidden items-center">
                        <button 
                            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                            className="p-2 text-secondary hover:text-accent-cyan transition-colors"
                        >
                            {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
                        </button>
                    </div>
                </div>
            </div>

            {/* Mobile Menu Dropdown */}
            {isMobileMenuOpen && (
                <div className="md:hidden bg-[#050505]/95 backdrop-blur-2xl border-b border-white/10 px-6 pt-4 pb-8 space-y-6 animate-in slide-in-from-top-2 duration-300">
                    <nav className="flex flex-col gap-5">
                        <Link to="/dashboard" onClick={() => setIsMobileMenuOpen(false)} className="text-lg font-medium text-secondary hover:text-accent-cyan transition-colors">Dashboard</Link>
                        <Link to="/courses" onClick={() => setIsMobileMenuOpen(false)} className="text-lg font-medium text-secondary hover:text-accent-purple transition-colors">My Courses</Link>
                        <Link to="/community" onClick={() => setIsMobileMenuOpen(false)} className="text-lg font-medium text-secondary hover:text-primary transition-colors">Community</Link>
                        <Link to="/admin" onClick={() => setIsMobileMenuOpen(false)} className="text-lg font-medium text-secondary hover:text-primary transition-colors">Admin</Link>
                    </nav>
                    
                    <div className="pt-6 border-t border-white/10 flex items-center justify-between">
                        <div className="flex items-center gap-6">
                            <button className="flex items-center justify-center p-2.5 rounded-full bg-white/5 text-primary hover:bg-white/10 hover:text-accent-cyan transition-all">
                                <Search size={22} />
                            </button>
                            <button className="flex items-center justify-center p-2.5 rounded-full bg-white/5 text-primary hover:bg-white/10 hover:text-accent-purple transition-all relative">
                                <Bell size={22} />
                                <span className="absolute top-2 right-2 w-2 h-2 bg-accent-cyan rounded-full border border-background"></span>
                            </button>
                        </div>

                        {session ? (
                            <div className="flex items-center gap-4">
                                <div className="h-10 w-10 rounded-full bg-white/[0.03] border border-white/10 flex items-center justify-center">
                                    <User size={20} className="text-primary" />
                                </div>
                                <button onClick={handleLogout} className="text-secondary hover:text-red-400 transition-colors p-2">
                                    <LogOut size={20} />
                                </button>
                            </div>
                        ) : (
                            <Link to="/auth" onClick={() => setIsMobileMenuOpen(false)}>
                                <Button variant="cyan" className="text-sm px-6 py-2.5 font-bold !text-background rounded-full">Login</Button>
                            </Link>
                        )}
                    </div>
                </div>
            )}
        </header>
    );
}

import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabaseClient';
import Button from './Button';
import { LogOut, User } from 'lucide-react';

export default function Navbar({ session }) {
    const [scrolled, setScrolled] = useState(false);
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

                <div className="flex items-center gap-3">
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

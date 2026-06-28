import React from 'react';

export default function Footer() {
    return (
        <footer className="w-full bg-dark rounded-t-[4rem] mt-[-4rem] pt-24 pb-12 px-6 md:px-12 lg:px-24 z-20 relative">
            <div className="max-w-6xl mx-auto">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-20">

                    <div className="md:col-span-2">
                        <div className="font-sans font-bold text-3xl tracking-tight text-primary mb-4">
                            EDU-VLE<span className="text-accent-cyan">.</span>
                        </div>
                        <p className="font-sans text-secondary max-w-sm mb-8 leading-relaxed">
                            A premium, open-access virtual learning environment for Edexcel Physics revision. Designed for mastery.
                        </p>
                        {/* System Status */}
                        <div className="inline-flex items-center gap-3 px-4 py-2 rounded-full border border-white/5 bg-white/5">
                            <div className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse"></div>
                            <span className="font-mono flex text-[10px] uppercase tracking-widest text-secondary">System Operational</span>
                        </div>
                    </div>

                    <div>
                        <h6 className="font-sans font-bold text-primary mb-6 uppercase text-sm tracking-widest">Navigation</h6>
                        <ul className="space-y-4 font-sans text-secondary text-sm">
                            <li><a href="#" className="hover:text-accent-cyan transition-colors duration-300">IGCSE Dashboard</a></li>
                            <li><a href="#" className="hover:text-accent-purple transition-colors duration-300">A-Level Dashboard</a></li>
                            <li><a href="#syllabus" className="hover:text-primary transition-colors duration-300">Methodology</a></li>
                        </ul>
                    </div>

                    <div>
                        <h6 className="font-sans font-bold text-primary mb-6 uppercase text-sm tracking-widest">Community & Legal</h6>
                        <ul className="space-y-4 font-sans text-secondary text-sm">
                            <li>
                                <a href="https://t.me/+K6arhuYMZss2YzE0" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 hover:text-accent-cyan transition-colors duration-300 font-bold">
                                    <svg className="w-4 h-4 text-[#0088cc]" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M12 0C5.372 0 0 5.373 0 12s5.372 12 12 12 12-5.373 12-12S18.628 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.15-.277.275-.58.275l.213-3.04 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.808.956z" />
                                    </svg>
                                    Join Telegram
                                </a>
                            </li>
                            <li><a href="#" className="hover:text-primary transition-colors duration-300">Privacy Policy</a></li>
                            <li><a href="#" className="hover:text-primary transition-colors duration-300">Terms of Service</a></li>
                        </ul>
                    </div>
                </div>

                <div className="pt-8 border-t border-white/10 flex flex-col md:flex-row justify-between items-center gap-4">
                    <p className="font-sans text-secondary/50 text-xs">
                        © {new Date().getFullYear()} EDU-VLE. All rights reserved.
                    </p>
                    <div className="font-mono text-secondary/30 text-[10px]">
                        BUILD_ID: B_7A3F9X
                    </div>
                </div>
            </div>
        </footer>
    );
}

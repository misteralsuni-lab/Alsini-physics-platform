import React from 'react';
import Button from './Button';

export default function CTA() {
    return (
        <section className="w-full py-40 px-6 md:px-12 lg:px-24 bg-surface z-10 relative">
            <div className="max-w-6xl mx-auto text-center mb-20">
                <h2 className="font-sans font-bold text-sm tracking-widest text-accent-cyan uppercase mb-4">Commence Protocol</h2>
                <h3 className="font-drama italic text-5xl md:text-7xl text-primary">Select your exam route.</h3>
                <p className="mt-6 font-sans text-secondary max-w-2xl mx-auto text-lg">
                    Begin your revision journey instantly. No login required.
                </p>
            </div>

            <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* IGCSE Card */}
                <div className="group relative bg-background rounded-[3rem] p-12 border border-white/5 hover:border-accent-cyan/50 transition-colors duration-500 overflow-hidden flex flex-col items-center text-center">
                    <div className="absolute inset-0 bg-gradient-to-b from-accent-cyan/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>

                    <div className="relative z-10">
                        <h4 className="font-mono text-xl text-accent-cyan mb-2">Level 1</h4>
                        <h5 className="font-sans font-bold text-4xl text-primary mb-6">Edexcel IGCSE</h5>
                        <ul className="text-secondary font-sans text-sm space-y-4 mb-10 text-left w-full max-w-[240px] mx-auto">
                            <li className="flex items-center gap-3"><span className="text-accent-cyan">✓</span> Core & Extended Content</li>
                            <li className="flex items-center gap-3"><span className="text-accent-cyan">✓</span> Interactive Quizzes</li>
                            <li className="flex items-center gap-3"><span className="text-accent-cyan">✓</span> Full Past Paper DB</li>
                        </ul>
                        <Button variant="outline" className="w-full justify-center">Enter IGCSE Dashboard</Button>
                    </div>
                </div>

                {/* A-Level Card */}
                <div className="group relative bg-dark rounded-[3rem] p-12 border border-accent-purple/30 shadow-[0_0_30px_rgba(123,97,255,0.1)] hover:border-accent-purple/60 hover:shadow-[0_0_50px_rgba(123,97,255,0.2)] transition-all duration-500 overflow-hidden flex flex-col items-center text-center">
                    <div className="absolute inset-0 bg-gradient-to-b from-accent-purple/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>

                    <div className="relative z-10">
                        <h4 className="font-mono text-xl text-accent-purple mb-2">Level 2</h4>
                        <h5 className="font-sans font-bold text-4xl text-primary mb-6">Edexcel A-Level</h5>
                        <ul className="text-secondary font-sans text-sm space-y-4 mb-10 text-left w-full max-w-[240px] mx-auto">
                            <li className="flex items-center gap-3"><span className="text-accent-purple">✓</span> AS & A2 Modules</li>
                            <li className="flex items-center gap-3"><span className="text-accent-purple">✓</span> Core Practical Analysis</li>
                            <li className="flex items-center gap-3"><span className="text-accent-purple">✓</span> Synoptic Question Training</li>
                        </ul>
                        <Button variant="accent" className="w-full justify-center">Enter A-Level Dashboard</Button>
                    </div>
                </div>
            </div>
        </section>
    );
}

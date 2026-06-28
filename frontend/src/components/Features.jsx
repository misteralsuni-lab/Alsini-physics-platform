import React, { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
// --- CARD 1: Diagnostic Shuffler ---
function DiagnosticShuffler() {

    const [cards, setCards] = useState([
        { id: 1, title: 'Topic 1: Mechanics', color: 'bg-accent-purple/10 border-accent-purple/20 text-accent-purple' },
        { id: 2, title: 'Topic 2: Waves & Particle Nature', color: 'bg-accent-cyan/10 border-accent-cyan/20 text-accent-cyan' },
        { id: 3, title: 'Topic 3: Electric Circuits', color: 'bg-secondary/10 border-secondary/20 text-secondary' },
    ]);

    useEffect(() => {
        const interval = setInterval(() => {
            setCards((prev) => {
                const newCards = [...prev];
                const last = newCards.pop();
                newCards.unshift(last);
                return newCards;
            });
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="relative w-full h-48 flex items-center justify-center pointer-events-none">
            {cards.map((item, index) => {

                const scale = 1 - index * 0.05;
                const translateY = index * 12;
                const zIndex = 30 - index;
                const opacity = 1 - index * 0.3;

                return (
                    <div
                        key={item.id}
                        className={`absolute w-full max-w-[240px] p-4 rounded-2xl border backdrop-blur-md transition-all duration-700 ease-[cubic-bezier(0.34,1.56,0.64,1)] ${item.color}`}
                        style={{
                            transform: `translateY(${translateY}px) scale(${scale})`,
                            zIndex,
                            opacity,
                        }}
                    >
                        <div className="flex items-center gap-3">
                            <div className="w-2 h-2 rounded-full animate-pulse bg-current"></div>
                            <span className="font-mono text-xs">{item.title}</span>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

// --- CARD 2: Telemetry Typewriter ---
function TelemetryTypewriter() {
    const [text, setText] = useState('');
    const [cursorVisible, setCursorVisible] = useState(true);
    const fullText = "Status: OK\n> Initializing PhET Simulation...\n> Embedded Video Lesson Ready.\n> Past Paper DB Connected.\n> Awaiting Input...";

    useEffect(() => {
        let index = 0;
        const typeInterval = setInterval(() => {
            if (index <= fullText.length) {
                setText(fullText.slice(0, index));
                index++;
            } else {
                clearInterval(typeInterval);
            }
        }, 50);

        const blinkInterval = setInterval(() => {
            setCursorVisible(v => !v);
        }, 500);

        return () => {
            clearInterval(typeInterval);
            clearInterval(blinkInterval);
        };
    }, []);

    return (
        <div className="relative w-full h-48 bg-dark/50 rounded-2xl border border-secondary/10 p-4 font-mono text-xs flex flex-col pointer-events-none overflow-hidden">
            <div className="flex items-center gap-2 mb-3 pb-3 border-b border-secondary/10">
                <div className="w-2 h-2 rounded-full bg-accent-cyan animate-pulse"></div>
                <span className="text-secondary tracking-widest uppercase text-[10px]">Live Telemetry</span>
            </div>
            <div className="text-primary whitespace-pre-wrap leading-relaxed opacity-80">
                {text}<span className={`text-accent-cyan ${cursorVisible ? 'opacity-100' : 'opacity-0'}`}>_</span>
            </div>
        </div>
    );
}

// --- CARD 3: Cursor Protocol Scheduler ---
function CursorProtocolScheduler() {
    const svgRef = useRef(null);
    const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

    useEffect(() => {
        let ctx = gsap.context(() => {
            const tl = gsap.timeline({ repeat: -1, repeatDelay: 1 });
            // starting pos
            tl.set("#cursor-icon", { x: 200, y: 150, opacity: 0 })
                .to("#cursor-icon", { opacity: 1, duration: 0.3 })
                .to("#cursor-icon", { x: 35, y: 40, duration: 1, ease: "power2.inOut" })
                .to("#cursor-icon", { scale: 0.8, duration: 0.1, yoyo: true, repeat: 1 })
                .to("#day-1", { backgroundColor: "rgba(123, 97, 255, 0.2)", borderColor: "rgba(123, 97, 255, 0.5)", color: "#7B61FF", duration: 0.2 }, "-=0.1")
                .to("#cursor-icon", { x: 95, y: 40, duration: 0.8, ease: "power2.inOut", delay: 0.5 })
                .to("#cursor-icon", { scale: 0.8, duration: 0.1, yoyo: true, repeat: 1 })
                .to("#day-3", { backgroundColor: "rgba(34, 211, 238, 0.2)", borderColor: "rgba(34, 211, 238, 0.5)", color: "#22D3EE", duration: 0.2 }, "-=0.1")
                .to("#cursor-icon", { x: 180, y: 120, duration: 0.8, ease: "power2.inOut", delay: 0.5 })
                .to("#cursor-icon", { scale: 0.8, duration: 0.1, yoyo: true, repeat: 1 })
                .to("#save-btn", { scale: 0.95, duration: 0.1, yoyo: true, repeat: 1 }, "-=0.1")
                .to("#cursor-icon", { opacity: 0, duration: 0.3, delay: 0.5 })
                .to(["#day-1", "#day-3"], { clearProps: "all", duration: 0.5 }); // reset
        }, svgRef);
        return () => ctx.revert();
    }, []);

    return (
        <div ref={svgRef} className="relative w-full h-48 bg-dark/50 rounded-2xl border border-secondary/10 p-4 font-mono text-xs flex flex-col justify-center pointer-events-none">
            <div className="flex gap-2 justify-center mb-6">
                {days.map((day, i) => (
                    <div key={i} id={`day-${i}`} className="w-8 h-8 rounded-md border border-secondary/20 flex items-center justify-center text-secondary transition-colors duration-300">
                        {day}
                    </div>
                ))}
            </div>
            <div className="flex justify-center mt-2">
                <div id="save-btn" className="px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-primary/70 text-[10px] uppercase tracking-wider">
                    Save Protocol
                </div>
            </div>

            {/* SVG Cursor */}
            <svg id="cursor-icon" className="absolute top-0 left-0 w-5 h-5 text-white drop-shadow-md z-10" fill="currentColor" viewBox="0 0 24 24" style={{ transform: 'translate(200px, 150px)' }}>
                <path d="M7 2l12 11.2-5.8.5 3.3 7.3-2.2.9-3.2-7.4-4.4 5.2z" />
            </svg>
        </div>
    );
}

export default function Features() {
    return (
        <section id="syllabus" className="w-full py-32 px-6 md:px-12 lg:px-24 bg-surface z-10 relative">
            <div className="max-w-6xl mx-auto">
                <div className="mb-16">
                    <h2 className="font-sans font-bold text-sm tracking-widest text-accent-cyan uppercase mb-4">Core Architecture</h2>
                    <h3 className="font-drama italic text-5xl md:text-6xl text-primary leading-tight">Interactive functional <br /><span className="text-secondary">artifacts.</span></h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">

                    {/* Feature 1 */}
                    <div className="flex flex-col gap-6 bg-background rounded-[2.5rem] p-8 border border-white/5 shadow-xl hover:border-white/10 transition-colors duration-500">
                        <DiagnosticShuffler />
                        <div>
                            <h4 className="font-sans font-semibold text-lg text-primary mb-2">Structured Syllabus Mastery</h4>
                            <p className="font-sans text-sm text-secondary leading-relaxed">
                                Content is organised into intuitive, Moodle-style collapsible topic accordions for rapid navigation and frictionless revision.
                            </p>
                        </div>
                    </div>

                    {/* Feature 2 */}
                    <div className="flex flex-col gap-6 bg-background rounded-[2.5rem] p-8 border border-white/5 shadow-xl hover:border-white/10 transition-colors duration-500">
                        <TelemetryTypewriter />
                        <div>
                            <h4 className="font-sans font-semibold text-lg text-primary mb-2">Interactive Learning</h4>
                            <p className="font-sans text-sm text-secondary leading-relaxed">
                                Seamlessly embedded video lessons, PhET simulations, and structured past paper tasks provide dynamic cognitive engagement.
                            </p>
                        </div>
                    </div>

                    {/* Feature 3 */}
                    <div className="flex flex-col gap-6 bg-background rounded-[2.5rem] p-8 border border-white/5 shadow-xl hover:border-white/10 transition-colors duration-500">
                        <CursorProtocolScheduler />
                        <div>
                            <h4 className="font-sans font-semibold text-lg text-primary mb-2">FHEQ Level 7 Experience</h4>
                            <p className="font-sans text-sm text-secondary leading-relaxed">
                                A highly professional, distraction-free interface explicitly optimised for iPads, designed to mimic modern university platforms.
                            </p>
                        </div>
                    </div>

                </div>
            </div>
        </section>
    );
}

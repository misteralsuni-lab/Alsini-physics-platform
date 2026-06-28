import React, { useLayoutEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

function Motif1() {
    return (
        <svg className="w-full h-full text-accent-cyan opacity-80" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor" strokeWidth="0.5" className="animate-[spin_20s_linear_infinite]" strokeDasharray="4 4" />
            <circle cx="50" cy="50" r="30" fill="none" stroke="currentColor" strokeWidth="1" className="animate-[spin_15s_linear_infinite_reverse]" strokeDasharray="10 5" />
            <circle cx="50" cy="50" r="20" fill="none" stroke="currentColor" strokeWidth="2" className="animate-[spin_10s_linear_infinite]" strokeDasharray="20 10" />
            <circle cx="50" cy="50" r="10" fill="currentColor" className="opacity-50 blur-[2px]" />
        </svg>
    );
}

function Motif2() {
    return (
        <div className="relative w-full h-full">
            <div className="absolute inset-0 bg-[radial-gradient(var(--tw-colors-secondary)_1px,transparent_1px)] [background-size:20px_20px] opacity-20"></div>
            <div className="absolute top-0 left-0 w-full h-[2px] bg-accent-purple shadow-[0_0_15px_rgba(123,97,255,0.8)] animate-[translateY_3s_ease-in-out_infinite_alternate]" style={{ animationName: 'scan' }}></div>
            <style>{`
        @keyframes scan {
          0% { transform: translateY(0); }
          100% { transform: translateY(300px); }
        }
      `}</style>
        </div>
    );
}

function Motif3() {
    const pathRef = useRef(null);

    useLayoutEffect(() => {
        gsap.to(pathRef.current, {
            strokeDashoffset: 0,
            duration: 2,
            ease: 'none',
            repeat: -1,
        });
    }, []);

    return (
        <svg className="w-full h-full text-accent-cyan drop-shadow-[0_0_10px_rgba(34,211,238,0.5)]" viewBox="0 -50 200 100" preserveAspectRatio="none">
            <path
                ref={pathRef}
                d="M 0 0 L 40 0 L 50 -40 L 60 40 L 70 -20 L 80 10 L 90 0 L 200 0"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                strokeDasharray="300"
                strokeDashoffset="300"
            />
        </svg>
    );
}

export default function Protocol() {
    const container = useRef(null);

    useLayoutEffect(() => {
        let ctx = gsap.context(() => {
            const cards = gsap.utils.toArray('.protocol-card');

            cards.forEach((card, i) => {
                ScrollTrigger.create({
                    trigger: card,
                    start: "top top",
                    endTrigger: container.current,
                    end: "bottom bottom",
                    pin: true,
                    pinSpacing: false,
                    scrub: true,
                });

                if (i < cards.length - 1) {
                    gsap.to(card, {
                        scale: 0.9,
                        opacity: 0.5,
                        filter: 'blur(10px)',
                        scrollTrigger: {
                            trigger: cards[i + 1],
                            start: "top bottom",
                            end: "top top",
                            scrub: true,
                        }
                    });
                }
            });
        }, container);
        return () => ctx.revert();
    }, []);

    const steps = [
        {
            num: "01",
            title: "THE FOUNDATION",
            desc: "A rigorous grounding in Edexcel specification requirements, ensuring absolute clarity on core physical principles.",
            motif: <Motif1 />
        },
        {
            num: "02",
            title: "THE SYNTHESIS",
            desc: "Connecting discrete concepts through interactive simulations and visual modeling to build deep tuition intuition.",
            motif: <Motif2 />
        },
        {
            num: "03",
            title: "THE APPLICATION",
            desc: "Mastering exam technique with structured past paper exposure under timed conditions.",
            motif: <Motif3 />
        }
    ];

    return (
        <section ref={container} className="relative w-full bg-background" id="methodology">
            <div className="pb-32 pt-16 text-center">
                <h2 className="font-sans font-bold tracking-widest text-accent-purple uppercase text-sm mb-4">Methodology</h2>
                <h3 className="font-drama italic text-5xl md:text-6xl text-primary">The Revision Protocol</h3>
            </div>

            <div className="relative w-full pb-[100vh]">
                {steps.map((step, i) => (
                    <div
                        key={i}
                        className="protocol-card absolute top-0 left-0 w-full h-[100vh] flex items-center justify-center p-6"
                        style={{ zIndex: i }}
                    >
                        <div className="w-full max-w-5xl h-[70vh] bg-surface/80 backdrop-blur-3xl rounded-[3rem] border border-white/10 shadow-2xl flex flex-col md:flex-row overflow-hidden relative">

                            <div className="flex-1 p-12 md:p-20 flex flex-col justify-center relative z-10">
                                <div className="font-mono text-accent-cyan text-xl mb-4 tracking-widest">{step.num} //</div>
                                <h4 className="font-sans font-bold text-4xl md:text-5xl text-primary mb-6">{step.title}</h4>
                                <p className="font-sans text-lg text-secondary leading-relaxed max-w-md">
                                    {step.desc}
                                </p>
                            </div>

                            <div className="flex-1 bg-dark/50 relative overflow-hidden flex items-center justify-center p-12">
                                {/* SVG Motif Container */}
                                <div className="w-full h-full max-w-[300px] max-h-[300px] relative">
                                    {step.motif}
                                </div>
                            </div>

                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}

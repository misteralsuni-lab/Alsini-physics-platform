import React, { useLayoutEffect, useRef } from 'react';
import gsap from 'gsap';
import Button from './Button';

export default function Hero() {
    const container = useRef(null);

    useLayoutEffect(() => {
        let ctx = gsap.context(() => {
            gsap.from(".hero-anim", {
                y: 40,
                opacity: 0,
                duration: 1.2,
                stagger: 0.15,
                ease: "power3.out",
                delay: 0.2
            });
        }, container);
        return () => ctx.revert();
    }, []);

    return (
        <section
            ref={container}
            className="relative w-full min-h-[100dvh] overflow-hidden flex items-center justify-start pt-40 pb-24 px-6 md:px-12 lg:px-24"
        >
            {/* Background Image with Overlay */}
            <div className="absolute inset-0 z-0">
                <img
                    src="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=2564&auto=format&fit=crop"
                    alt="Abstract dark bioluminescence"
                    className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-background via-background/80 to-transparent"></div>
                <div className="absolute inset-0 bg-background/40"></div> {/* Additional darkening to avoid eye strain */}
            </div>

            {/* Content */}
            <div className="relative z-10 w-full max-w-3xl">
                <h1 className="flex flex-col">
                    <span className="hero-anim font-sans font-bold text-sm md:text-base lg:text-lg text-secondary tracking-widest uppercase mb-3 ml-1">
                        PHYSICS MASTERY BEYOND
                    </span>
                    <span className="hero-anim font-drama italic text-6xl md:text-8xl lg:text-[9rem] leading-[0.8] text-primary tracking-tighter">
                        limits.
                    </span>
                </h1>

                <p className="hero-anim mt-12 font-sans text-lg md:text-xl text-secondary max-w-xl font-light leading-relaxed">
                    EDU-VLE is a premium, open-access virtual learning environment for Edexcel IGCSE and A-Level revision.
                </p>

                <div className="hero-anim mt-10 mb-8 flex flex-col gap-8">
                    <div className="flex flex-wrap gap-4">
                        <Button variant="cyan">Select Exam Route</Button>
                        <Button variant="outline">Explore Methodology</Button>
                        <Button
                            variant="outline"
                            href="https://t.me/+K6arhuYMZss2YzE0"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="!border-[#0088cc]/50 hover:!bg-[#0088cc]/10 !text-[#0088cc]"
                        >
                            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 0C5.372 0 0 5.373 0 12s5.372 12 12 12 12-5.373 12-12S18.628 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.15-.277.275-.58.275l.213-3.04 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.808.956z" />
                            </svg>
                            Join Telegram Community
                        </Button>
                    </div>

                    <div className="flex items-center gap-5 p-4 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm w-fit transition-all hover:border-[#0088cc]/50 hover:bg-[#0088cc]/5 duration-500">
                        <div className="bg-white p-2 rounded-xl shadow-lg">
                            <img
                                src="/telegram-qr.png"
                                alt="EDU-VLE Telegram QR Code"
                                className="w-16 h-16 md:w-20 md:h-20 object-contain"
                            />
                        </div>
                        <div className="flex flex-col pr-4">
                            <span className="font-sans font-bold text-primary text-sm md:text-base tracking-wide">Scan to Join</span>
                            <span className="font-sans text-xs md:text-sm text-secondary/80">Connect with the community</span>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}

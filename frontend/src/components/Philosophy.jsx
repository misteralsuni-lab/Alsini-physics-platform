import React, { useLayoutEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export default function Philosophy() {
    const container = useRef(null);

    useLayoutEffect(() => {
        let ctx = gsap.context(() => {
            // Parallax background
            gsap.to('.philo-bg', {
                yPercent: 20,
                ease: 'none',
                scrollTrigger: {
                    trigger: container.current,
                    start: 'top bottom',
                    end: 'bottom top',
                    scrub: true,
                },
            });

            // Text reveal
            gsap.from('.philo-text', {
                y: 50,
                opacity: 0,
                duration: 1.2,
                stagger: 0.2,
                ease: 'power3.out',
                scrollTrigger: {
                    trigger: container.current,
                    start: 'top 70%',
                },
            });
        }, container);
        return () => ctx.revert();
    }, []);

    return (
        <section ref={container} className="relative w-full py-40 overflow-hidden bg-dark flex items-center justify-center">
            {/* Background Image Parallax */}
            <div className="absolute inset-x-0 -top-20 -bottom-20 z-0 philo-bg">
                <img
                    src="https://images.unsplash.com/photo-1550684848-fac1c5b4e853?q=80&w=2070&auto=format&fit=crop"
                    alt="Bioluminescent texture"
                    className="w-full h-full object-cover opacity-10"
                />
                <div className="absolute inset-0 bg-dark/60"></div>
            </div>

            <div className="relative z-10 max-w-5xl mx-auto px-6 md:px-12 text-center flex flex-col items-center gap-12">
                <p className="philo-text font-sans text-xl md:text-2xl text-secondary max-w-2xl leading-relaxed">
                    Most revision platforms focus on: fragmented content and superficial metrics.
                </p>
                <p className="philo-text font-drama italic text-5xl md:text-7xl lg:text-[6rem] text-primary leading-tight tracking-tighter">
                    We focus on: deep <span className="text-accent-cyan">mastery.</span>
                </p>
            </div>
        </section>
    );
}

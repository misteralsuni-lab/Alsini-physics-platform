import React, { useRef } from 'react';

export default function Button({ children, className = '', variant = 'accent', onClick, href, target, rel }) {
    const btnRef = useRef(null);

    const baseClasses = "relative overflow-hidden rounded-[2rem] font-sans font-medium hover:scale-[1.03] transition-transform duration-300 pointer-events-auto inline-flex items-center justify-center gap-2";

    const style = { transitionTimingFunction: "cubic-bezier(0.25, 0.46, 0.45, 0.94)" };

    let variantClasses = "";
    let hoverOverlay = "";
    if (variant === 'accent') {
        variantClasses = "bg-accent-purple text-primary px-6 py-3";
        hoverOverlay = "bg-accent-cyan/20";
    } else if (variant === 'outline') {
        variantClasses = "border border-secondary/30 text-primary px-6 py-3 hover:border-accent-cyan/50 transition-colors";
        hoverOverlay = "bg-accent-cyan/10";
    } else if (variant === 'cyan') {
        variantClasses = "bg-accent-cyan text-background px-6 py-3";
        hoverOverlay = "bg-white/30";
    }

    const content = (
        <>
            <span className="relative z-10 flex items-center justify-center gap-2">{children}</span>
            <span className={`absolute inset-0 ${hoverOverlay} translate-y-[101%] group-hover:translate-y-0 transition-transform duration-300 ease-out`} />
        </>
    );

    // Security: Prevent reverse tabnabbing for external links
    let finalRel = rel;
    if (target === '_blank') {
        finalRel = rel ? `${rel} noopener noreferrer` : "noopener noreferrer";
    }

    if (href) {
        return (
            <a
                ref={btnRef}
                style={style}
                href={href}
                target={target}
                rel={finalRel}
                className={`${baseClasses} ${variantClasses} group ${className}`}
            >
                {content}
            </a>
        );
    }

    return (
        <button
            ref={btnRef}
            style={style}
            onClick={onClick}
            className={`${baseClasses} ${variantClasses} group ${className}`}
        >
            {content}
        </button>
    );
}

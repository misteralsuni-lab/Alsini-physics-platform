/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0f172a', // Deep slate grey
        surface: '#1e293b',    // Slightly lighter slate for cards
        primary: '#f8fafc',    // Off-white text
        secondary: '#94a3b8',  // Muted text
        accent: {
          purple: '#7B61FF',
          cyan: '#22D3EE',
        },
        dark: '#020617', // For the deepest backgrounds/footers
      },
      fontFamily: {
        sans: ['"Sora"', 'sans-serif'],
        drama: ['"Instrument Serif"', 'serif'],
        mono: ['"Fira Code"', 'monospace'],
      },
    },
  },
  plugins: [],
}

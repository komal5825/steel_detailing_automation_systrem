/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: '#0D1B3E', light: '#1A3A6B', dark: '#080F22' },
        steel: { DEFAULT: '#1A56A0', light: '#D6E8F7', muted: '#2563EB' },
        pass: { DEFAULT: '#16A34A', bg: '#DCFCE7' },
        fail: { DEFAULT: '#DC2626', bg: '#FEE2E2' },
        warn: { DEFAULT: '#D97706', bg: '#FEF3C7' },
        blocked: { DEFAULT: '#6B7280', bg: '#F3F4F6' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-in': 'slideIn 0.3s ease-out',
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        slideIn: { from: { transform: 'translateY(8px)', opacity: 0 }, to: { transform: 'translateY(0)', opacity: 1 } },
      },
    },
  },
  plugins: [],
};

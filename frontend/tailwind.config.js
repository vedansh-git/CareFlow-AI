/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cure: {
          bg: '#0c0d14',
          surface: '#12141f',
          card: '#181926',
          'card-hover': '#1e2030',
          border: 'rgba(255, 255, 255, 0.08)',
          'border-light': 'rgba(255, 255, 255, 0.12)',
          purple: {
            300: '#c4b5fd',
            400: '#a78bfa',
            500: '#8b5cf6',
            600: '#7059e2',
            700: '#5e43db',
            800: '#4c33bd',
            900: '#342187',
          },
          accent: '#6c5dd3',
          teal: '#14b8a6',
          coral: '#f43f5e',
          amber: '#f59e0b',
        },
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          500: '#0284c7',
          600: '#0369a1',
          700: '#035485',
          900: '#0c2a47',
        },
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
        '4xl': '2rem',
      },
      boxShadow: {
        'cure-glow': '0 0 25px rgba(112, 89, 226, 0.25)',
        'cure-card': '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
      },
    },
  },
  plugins: [],
}

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        clinical: {
          block: '#ef4444',
          high: '#f97316',
          moderate: '#f59e0b',
          info: '#3b82f6',
          unverified: '#8b5cf6',
          checked: '#14b8a6',
          bg: '#090d16',
          surface: '#0f172a',
          surfaceMuted: '#1e293b',
          border: '#334155',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}

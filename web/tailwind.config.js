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
        // BedLink Whisper Sage Design System Tokens
        bedlink: {
          canvas: '#F4F6F4',
          surface: '#FFFFFF',
          hover: '#EEF3EE',
          border: '#E1E7E1',
          borderStrong: '#C4CEBD',
          primary: '#2D6A4F',
          primaryDark: '#1B4D39',
          primarySoft: '#E8F5E9',
          text: '#1A2421',
          textMuted: '#5C6B64',
          headerBg: '#1A2421',
        },
        sage: {
          50: '#F4F6F4',
          100: '#EEF3EE',
          200: '#E1E7E1',
          300: '#C4CEBD',
          400: '#8A9991',
          500: '#5C6B64',
          600: '#3D5047',
          700: '#2D6A4F',
          800: '#1B4D39',
          900: '#1A2421',
          950: '#0F1714',
        },
        clinical: {
          // Warning & Status Colors (Preserved and Refined for high contrast on Sage canvas)
          block: '#E11D48',
          blockBg: '#FFF1F2',
          blockBorder: '#FECDD3',
          high: '#EA580C',
          highBg: '#FFF7ED',
          highBorder: '#FED7AA',
          moderate: '#D97706',
          moderateBg: '#FFFBEB',
          moderateBorder: '#FDE68A',
          info: '#1D4ED8',
          infoBg: '#EFF6FF',
          infoBorder: '#BFDBFE',
          unverified: '#7C3AED',
          unverifiedBg: '#FAF5FF',
          unverifiedBorder: '#DDD6FE',
          checked: '#2E7D32',
          checkedBg: '#E8F5E9',
          checkedBorder: '#A5D6A7',

          // Clinical Base UI (Aligned to BedLink Whisper Sage)
          bg: '#F4F6F4',
          surface: '#FFFFFF',
          surfaceMuted: '#EEF3EE',
          border: '#E1E7E1',
          borderStrong: '#C4CEBD',
          text: '#1A2421',
          textMuted: '#5C6B64',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      }
    },
  },
  plugins: [],
}


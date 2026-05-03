export default {
  darkMode: 'class',
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── Light mode (Linear light) ──────────────────────
        ml: {
          yellow:       '#FFE600',
          'yellow-dark':'#F5DC00',
          blue:         '#5E6AD2',  // Linear purple-blue
          'blue-dark':  '#4A55BE',
          'blue-darker':'#3A43A0',
          gray:         '#E4E4E7',
          'gray-dark':  '#A1A1AA',
          'gray-bg':    '#F4F4F5',
          text:         '#18181B',
          'text-soft':  '#71717A',
          // ── Dark mode (Linear dark) ─────────────────────
          'dark-bg':      '#0B0B0F',
          'dark-surface': '#111116',
          'dark-card':    '#16161C',
          'dark-border':  '#1E1E26',
          'dark-hover':   '#1A1A22',
          // ── Accent verde hacker ─────────────────────────
          'green':        '#22C55E',
          'green-bright': '#4ADE80',
          'green-dim':    '#16A34A',
          'green-muted':  '#14532D',
        },
        // Estado semánticos
        status: {
          ok:       '#22C55E',
          error:    '#EF4444',
          warn:     '#F59E0B',
          info:     '#5E6AD2',
          neutral:  '#71717A',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['10px', '14px'],
      },
      borderRadius: {
        'xl':  '10px',
        '2xl': '14px',
      },
      boxShadow: {
        'card':       '0 1px 3px 0 rgba(0,0,0,.06), 0 1px 2px -1px rgba(0,0,0,.06)',
        'card-hover': '0 4px 12px 0 rgba(0,0,0,.1)',
        'green-glow': '0 0 20px 0 rgba(34,197,94,.15)',
        'green-sm':   '0 0 8px 0 rgba(34,197,94,.20)',
      },
      animation: {
        'slide-in': 'slideIn 0.2s ease-out',
        'fade-in':  'fadeIn 0.15s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    }
  },
  plugins: []
}

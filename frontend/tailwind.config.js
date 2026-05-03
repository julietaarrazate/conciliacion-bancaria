
export default {
  darkMode: 'class',
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ml: {
          // Modo claro — identidad original
          yellow: '#FFE600',
          'yellow-dark': '#FFDB15',
          blue: '#3483FA',
          'blue-dark': '#2968C8',
          'blue-darker': '#1B3F73',
          gray: '#EBEBEB',
          'gray-dark': '#999999',
          'gray-bg': '#F5F5F5',
          text: '#333333',
          'text-soft': '#666666',
          // Modo oscuro — estética fintech/coder
          'dark-bg':      '#09090B',  // casi negro
          'dark-surface': '#18181B',  // zinc-900
          'dark-card':    '#1C1C1F',
          'dark-border':  '#27272A',
          'green':        '#22C55E',  // acento principal dark
          'green-bright': '#4ADE80',  // hover
          'green-dim':    '#15803D',  // active/pressed
          'green-glow':   '#22C55E33', // glow sutil
        },
        primary: {
          50: '#EFF6FF',
          100: '#DBEAFE',
          500: '#3483FA',
          600: '#2968C8',
          700: '#1B3F73'
        }
      },
      fontFamily: {
        sans: ['Proxima Nova', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace']
      },
      boxShadow: {
        'green-glow': '0 0 16px 0 rgba(34,197,94,0.25)',
        'green-glow-sm': '0 0 8px 0 rgba(34,197,94,0.20)',
      }
    }
  },
  plugins: []
}

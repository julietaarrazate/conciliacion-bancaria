/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#1d4ed8', hover: '#1e40af' },
        success: '#16a34a',
        danger: '#dc2626',
        warning: '#d97706',
      },
    },
  },
  plugins: [],
}

/** Theme MercadoLibre + Dark Mode */
export default {
  darkMode: 'class',
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // MercadoLibre brand
        ml: {
          yellow: '#FFE600',
          'yellow-dark': '#FFDB15',
          blue: '#3483FA',
          'blue-dark': '#2968C8',
          'blue-darker': '#1B3F73',
          gray: '#EBEBEB',
          'gray-dark': '#999999',
          'gray-bg': '#F5F5F5',
          text: '#333333',
          'text-soft': '#666666'
        },
        // legacy primary -> ml.blue
        primary: {
          50: '#EFF6FF',
          100: '#DBEAFE',
          500: '#3483FA',
          600: '#2968C8',
          700: '#1B3F73'
        }
      },
      fontFamily: {
        sans: ['Proxima Nova', 'Helvetica', 'Arial', 'sans-serif']
      }
    }
  },
  plugins: []
}

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        'lh-red': '#C61531',
        'lh-orange': '#F15A24',
        'lh-dark': '#262626',
        'lh-navy': '#1B1464',
        'lh-cream': '#FAF7F2',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

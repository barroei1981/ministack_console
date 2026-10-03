/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'aws-blue': '#232f3e',
        'aws-orange': '#ff9900',
        'aws-gray-light': '#f2f3f3',
        'aws-gray-dark': '#545b64',
        'aws-border': '#d5dbdb',
      },
    },
  },
  plugins: [],
}

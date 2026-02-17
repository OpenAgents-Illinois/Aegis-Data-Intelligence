/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        aegis: {
          50: "#eef7ff",
          100: "#d9edff",
          200: "#bce0ff",
          300: "#8ecdff",
          400: "#59b0ff",
          500: "#338dff",
          600: "#1c6df5",
          700: "#1557e1",
          800: "#1746b6",
          900: "#193d8f",
          950: "#142757",
        },
      },
    },
  },
  plugins: [],
};

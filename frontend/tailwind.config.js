/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        coal: {
          950: "#0d1110",
          900: "#111816",
          850: "#17201d",
          800: "#1d2824",
        },
        ember: {
          300: "#fbbf77",
          400: "#fb923c",
          500: "#f97316",
          600: "#ea580c",
        },
      },
      boxShadow: {
        ember: "0 14px 34px rgba(249, 115, 22, 0.28)",
        panel: "0 18px 52px rgba(3, 7, 18, 0.34)",
      },
    },
  },
  plugins: [],
};

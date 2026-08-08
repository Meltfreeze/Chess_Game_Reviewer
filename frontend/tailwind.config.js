/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        boardLight: "#EBECD0",
        boardDark: "#779556",
        panel: "#302e2b",
        panelBorder: "#403e3b",
        accent: "#e58f2a",
      },
    },
  },
  plugins: [],
};

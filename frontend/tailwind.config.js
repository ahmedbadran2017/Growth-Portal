/** @type {import('tailwindcss').Config} */
// Justyol house palette, shared with Task Hub so the two portals are visibly
// one product. Verdict colours are the only additions: they carry meaning, so
// they are named for the verdict rather than for the hue.
export default {
  content: ["./index.html", "./src/**/*.{vue,js}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#fafaf9", 100: "#f5f5f4", 200: "#e7e5e4",
          300: "#d6d3d1", 400: "#a8a29e", 500: "#78716c",
          600: "#57534e", 700: "#44403c", 800: "#292524",
          900: "#1c1917",
        },
        brand: {
          50: "#fdf5f3", 100: "#fbe6e0", 200: "#f6ccbf",
          300: "#eea894", 400: "#e17f62", 500: "#d45d3e",
          600: "#c4492a", 700: "#a33a22", 800: "#852f1e",
          900: "#6d291d",
        },
      },
      // Grow / Fix / Kill / Dormant / Watch. One colour per verdict and nothing
      // else on the page uses them, so a red here always means money leaving.
      fontFamily: {
        sans: ["Inter", "Noto Sans Arabic", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};

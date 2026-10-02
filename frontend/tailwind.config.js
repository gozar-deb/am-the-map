/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#0A0E13",
        panel: "#10161D",
        panel2: "#141B23",
        hairline: "#1E2830",
        signal: "#4FD1E8",
        movement: "#FFB454",
        danger: "#E85D4D",
        ink: "#E7EDF2",
        muted: "#6B7A87",
        muted2: "#3E4A55",
      },
      fontFamily: {
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
        sans: ["IBM Plex Sans", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 0 0 1px #1E2830",
      },
    },
  },
  plugins: [],
};

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{html,js,ts,jsx,tsx,vue}",
    "./templates/**/*.{html,js}",
    "./src/hyperadmin/templates/**/*.{html,js}",
    "./examples/**/*.{html,js,py}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
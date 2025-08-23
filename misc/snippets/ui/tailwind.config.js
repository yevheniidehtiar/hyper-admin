/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "../sqladmin/templates/**/*.html",
    "../sqladmin/statics/js/**/*.js",
    "./src/**/*.{html,js}",
    "./node_modules/flowbite/**/*.js"
  ],
  theme: {
    extend: {
      // Custom theme extensions for SQLAdmin
      colors: {
        'admin-primary': {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        }
      }
    },
  },
  plugins: [
    require('flowbite/plugin')
  ],
}
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/templates/**/*.html', // Adjust this to point to your templates directory
    './app/static/**/*.js',      // If you use any JavaScript files
  ],
  theme: {
    extend: {
      // Add any custom theme settings here
    },
  },
  plugins: [],
};



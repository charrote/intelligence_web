const { defineConfig } = require('vite')
module.exports = defineConfig({
  server: {
    allowedHosts: ['activedemo.nat.ywapi.com']
  }
})
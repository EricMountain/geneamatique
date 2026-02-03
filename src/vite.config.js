import { defineConfig } from 'vite';

export default defineConfig({
    base: './',
    build: {
        // build directly into lambda package so Terraform will pick it up
        outDir: '../lambda/dist',
        assetsDir: 'assets'
    },
    // Proxy /api/* to local lambda dev server during `npm run dev`
    server: {
        proxy: {
            '/api': process.env.API_PROXY_TARGET || 'http://localhost:3001'
        }
    }
});

import { defineConfig } from 'vite';

export default defineConfig({
    base: './',
    build: {
        // build directly into lambda package so Terraform will pick it up
        outDir: '../lambda/dist',
        assetsDir: 'assets'
    }
});

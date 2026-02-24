import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        globals: true,
        include: [
            'frontend_public/static/js/**/*.test.js',
            'frontend_private/static/private/js/**/*.test.js'
        ],
        exclude: [
            '**/node_modules/**',
            '**/dist/**',
            '**/vendors/**'
        ]
    }
});


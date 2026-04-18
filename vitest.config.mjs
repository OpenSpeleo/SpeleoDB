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
        ],
        // Hide console output (stdout/stderr) from tests that pass. Error-path
        // tests deliberately trigger `console.error(...)` in production code,
        // and their noise buried real failures in the output. When a test
        // fails, its intercepted output is still printed in full so you can
        // see exactly what happened.
        silent: 'passed-only'
    }
});


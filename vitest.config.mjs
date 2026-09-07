import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        globals: true,
        setupFiles: ['./frontend_common/test/setup.js'],
        // Vite and Tailwind builds spawn their own parallel work. Limiting
        // file workers prevents those builds from starving JSDOM test event
        // loops in constrained devcontainers and CI runners.
        maxWorkers: 4,
        experimental: {
            diagnostics: {
                // `vitest doctor` confirmed that the shared-environment and VM
                // alternatives fail this suite and the safe candidates save
                // less than 3%, so this recurring hint is not actionable.
                environment: false,
                isolate: false
            }
        },
        include: [
            'frontend_common/**/*.test.js',
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

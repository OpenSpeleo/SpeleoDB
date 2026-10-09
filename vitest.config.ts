import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';
import { sharedMapResolution } from './scripts/shared-map-packages.ts';

export default defineConfig({
    resolve: sharedMapResolution,
    test: {
        environment: 'jsdom',
        globals: true,
        testTimeout: 30_000,
        execArgv: ['--preload', fileURLToPath(new URL('./scripts/jsdom-runtime.ts', import.meta.url))],
        setupFiles: ['./frontend_common/test/setup.ts'],
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
            'frontend_common/**/*.test.ts',
            'frontend_errors/static/ts/**/*.test.ts',
            'frontend_public/static/ts/**/*.test.ts',
            'frontend_private/static/private/ts/**/*.test.ts'
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

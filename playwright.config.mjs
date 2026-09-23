import { defineConfig, devices } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export default defineConfig({
    testDir: './tests/browser',
    testMatch: '**/*.spec.mjs',
    fullyParallel: false,
    workers: 1,
    retries: 0,
    timeout: 120_000,
    expect: { timeout: 20_000 },
    outputDir: process.env.VIEWER_BROWSER_ARTIFACTS || join(tmpdir(), 'speleodb-viewer-browser'),
    reporter: 'list',
    use: {
        baseURL: process.env.VIEWER_BROWSER_BASE_URL || 'http://127.0.0.1:8000',
        viewport: { width: 1440, height: 1000 },
        ignoreHTTPSErrors: true,
        screenshot: 'only-on-failure',
        // Network traces would retain session cookies and the login payload.
        trace: 'off',
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 }, launchOptions: {
                args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
            } },
        },
        { name: 'webkit', use: { ...devices['Desktop Safari'], viewport: { width: 1440, height: 1000 } } },
    ],
});

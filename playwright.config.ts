import { defineConfig, devices } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { BROWSER_TEST_BUDGETS } from './tests/browser/budgets.ts';

const artifacts = process.env.VIEWER_BROWSER_ARTIFACTS || join(tmpdir(), 'speleodb-viewer-browser');

export default defineConfig({
    testDir: './tests/browser',
    testMatch: '**/*.spec.ts',
    fullyParallel: false,
    workers: 1,
    retries: 0,
    timeout: BROWSER_TEST_BUDGETS.testMs,
    expect: { timeout: BROWSER_TEST_BUDGETS.assertionMs },
    outputDir: artifacts,
    reporter: [['list'], ['json', { outputFile: join(artifacts, 'report.json') }]],
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

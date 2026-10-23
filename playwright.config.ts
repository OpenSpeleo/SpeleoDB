import { defineConfig, devices } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { BROWSER_TEST_BUDGETS } from './tests/browser/budgets.ts';

const artifacts = process.env.VIEWER_BROWSER_ARTIFACTS || join(tmpdir(), 'speleodb-viewer-browser');
const viewport = { width: 1280, height: 800 };

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
        viewport,
        // Ordinary UI checks do not need a globe-to-survey flight per startup.
        // Gesture scenarios explicitly select the motion policy they exercise.
        reducedMotion: 'reduce',
        ignoreHTTPSErrors: true,
        screenshot: 'only-on-failure',
        // Network traces would retain session cookies and the login payload.
        trace: 'off',
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'], viewport, launchOptions: {
                args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
            } },
        },
        // The Safari preset's DPR 2 quadruples software canvas work. These
        // scenarios protect CSS geometry and visible output at DPR 1.
        { name: 'webkit', use: { ...devices['Desktop Safari'], viewport, deviceScaleFactor: 1 } },
    ],
});

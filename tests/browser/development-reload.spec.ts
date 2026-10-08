import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { build } from 'vite';
import path from 'node:path';

let client = '';
test.beforeAll(async () => {
    const entry = 'virtual:development-reload-browser';
    const result = await build({
        configFile: false,
        logLevel: 'silent',
        plugins: [{
            name: 'reload-browser-entry',
            resolveId(id) { if (id === entry) return id; },
            load(id) {
                if (id === entry) return `import { startDevelopmentReload } from ${JSON.stringify(path.resolve('frontend_common/development/reload.ts'))}; startDevelopmentReload();`;
            },
        }],
        build: { write: false, minify: false, rolldownOptions: { input: entry } },
    });
    if ('on' in result) throw new Error('Unexpected watch build');
    const outputs = Array.isArray(result) ? result.flatMap(item => item.output) : result.output;
    const chunk = outputs.find(output => output.type === 'chunk' && output.isEntry);
    if (!chunk || chunk.type !== 'chunk') throw new Error('Missing compiled reload client');
    client = chunk.code;
});

async function fixture(page: Page) {
    const state = { rendered: 'session-a/1', published: 'session-a/1', navigations: 0, polls: 0, malformed: false };
    await page.route('**/__reload-test__/', async route => {
        state.navigations++;
        await route.fulfill({ contentType: 'text/html', body: `<html><body><p>Generation fixture</p><script type="module" src="/__reload-client__.js" data-speleodb-generation="${state.rendered}" data-speleodb-reload="/__reload-generation__/"></script></body></html>` });
    });
    await page.route('**/__reload-client__.js', route => route.fulfill({ contentType: 'application/javascript', body: client }));
    await page.route('**/__reload-generation__/', async route => {
        state.polls++;
        await route.fulfill({ contentType: 'application/json', body: state.malformed ? '{' : JSON.stringify({ generation: state.published }) });
    });
    return state;
}

test('development reload waits for publication and reloads exactly once to the completed generation', async ({ page }) => {
    const state = await fixture(page);
    await page.goto('/__reload-test__/');
    await expect.poll(() => state.polls).toBeGreaterThanOrEqual(2);
    expect(state.navigations).toBe(1);
    state.rendered = state.published = 'session-a/2';
    await expect.poll(() => state.navigations).toBe(2);
    await expect.poll(() => state.polls).toBeGreaterThanOrEqual(5);
    expect(state.navigations).toBe(2);
});

test('development reload compares the first response with rendered HTML and prevents a stale-page loop', async ({ page }) => {
    const state = await fixture(page);
    state.published = 'session-a/2';
    await page.goto('/__reload-test__/');
    await expect.poll(() => state.navigations).toBe(2);
    await expect.poll(() => state.polls).toBeGreaterThanOrEqual(4);
    expect(state.navigations).toBe(2);
    expect(await page.evaluate(() => sessionStorage.getItem('speleo_dev_reload_target'))).toBe('session-a/2');
});

test('development reload handles unavailable browser storage without navigating', async ({ page }) => {
    await page.addInitScript(() => {
        Object.defineProperty(window, 'sessionStorage', { get() { throw new Error('Storage unavailable'); } });
    });
    const state = await fixture(page);
    state.published = 'session-a/2';
    await page.goto('/__reload-test__/');
    await expect.poll(() => state.polls).toBeGreaterThanOrEqual(3);
    expect(state.navigations).toBe(1);
});

test('development reload ignores partial responses and recovers on completed publication', async ({ page }) => {
    const state = await fixture(page);
    state.malformed = true;
    await page.goto('/__reload-test__/');
    await expect.poll(() => state.polls).toBeGreaterThanOrEqual(2);
    expect(state.navigations).toBe(1);
    state.malformed = false;
    state.rendered = state.published = 'session-a/2';
    await expect.poll(() => state.navigations).toBe(2);
});

import { expect, test } from '@playwright/test';

test('completed asset builds require manual refresh without polling or automatic navigation', async ({ page }) => {
    let published = 'first';
    let navigations = 0;
    const generationRequests: string[] = [];
    const reloadClients: string[] = [];
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
        const pathname = new URL(request.url()).pathname;
        if (pathname.includes('/__assets__/generation/')) generationRequests.push(pathname);
        if (/\/(?:development\/)?reload(?:[-/.]|$)/.test(pathname)) reloadClients.push(pathname);
        if (request.isNavigationRequest() && request.frame() === page.mainFrame()) navigations++;
    });
    await page.route('**/__assets__/generation/', route => route.fulfill({
        contentType: 'application/json', body: JSON.stringify({ generation: `manual-build/${published === 'first' ? 1 : 2}` }),
    }));
    await page.route('**/login/', async route => {
        const response = await route.fetch();
        const html = await response.text();
        expect(html).not.toMatch(/data-speleodb-(?:generation|reload)/);
        // Retain the real Django template and bootstrap while exposing which
        // completed build a fresh document would receive.
        await route.fulfill({ response, body: html.replace('</head>', `<meta name="manual-build" content="${published}"></head>`) });
    });
    await page.addInitScript(() => {
        document.addEventListener('speleodb:controller-ready', () => {
            document.documentElement.dataset.bootstrapReady = 'true';
        }, { once: true });
    });
    await page.clock.install({ time: 0 });
    await page.clock.pauseAt(60_000);
    await page.goto('/login/');
    await expect(page.locator('html')).toHaveAttribute('data-bootstrap-ready', 'true');
    await expect(page.locator('[data-speleodb-generation], [data-speleodb-reload]')).toHaveCount(0);
    await expect(page.locator('meta[name="manual-build"]')).toHaveAttribute('content', 'first');
    expect(navigations).toBe(1);

    published = 'second';
    await page.clock.fastForward(300_000);
    await page.evaluate(() => {
        document.dispatchEvent(new Event('visibilitychange'));
        for (const event of ['focus', 'online', 'pageshow']) window.dispatchEvent(new Event(event));
    });
    await page.clock.fastForward(300_000);
    expect(navigations).toBe(1);
    expect(generationRequests).toEqual([]);
    expect(reloadClients).toEqual([]);
    await expect(page.locator('meta[name="manual-build"]')).toHaveAttribute('content', 'first');

    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-bootstrap-ready', 'true');
    await expect(page.locator('meta[name="manual-build"]')).toHaveAttribute('content', 'second');
    expect(navigations).toBe(2);
    expect(generationRequests).toEqual([]);
    expect(reloadClients).toEqual([]);
    expect(errors).toEqual([]);
});

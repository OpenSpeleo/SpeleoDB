import { expect, test } from '@playwright/test';
import { getV2ProjectsUploadUrl } from '@speleodb/api';
import type { ProjectUploadContext } from '../../ts-types/controllers/project-upload.ts';
import type { Page } from '@playwright/test';
import { login } from './viewer-fixture.ts';

/** Observe the normal bootstrap without importing or initializing controllers twice. */
async function observeControllers(page: Page) {
    await page.addInitScript(() => {
        document.addEventListener('speleodb:controller-ready', event => {
            if (event.target instanceof HTMLElement) {
                event.target.dataset.browserReady = 'true';
                event.target.dataset.browserStatus = 'ready';
            }
        });
        document.addEventListener('speleodb:controller-error', event => {
            if (!(event.target instanceof HTMLElement)) return;
            const error = (event as CustomEvent<{ error: unknown }>).detail.error;
            const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
            // Preserve the failure cause without retaining signed URLs or credentials.
            event.target.dataset.browserError = message.replace(/https?:\/\/[^\s]+/g, value => {
                try {
                    const url = new URL(value);
                    return `${url.origin}${url.pathname}`;
                } catch {
                    return '[URL]';
                }
            });
            event.target.dataset.browserStatus = 'error';
        });
    });
}

async function openController(page: Page, path: string, controller: string) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    const declaration = page.locator(`[data-speleodb-controller="${controller}"]`);
    await expect(declaration).toHaveAttribute('data-browser-status', /^(ready|error)$/);
    expect(await declaration.getAttribute('data-browser-error'), `${controller} initialization failed`).toBeNull();
    await expect(declaration).toHaveAttribute('data-browser-ready', 'true');
    await expect(page.locator('[data-browser-error]')).toHaveCount(0);
}

test.beforeEach(async ({ page }) => {
    await observeControllers(page);
    await login(page);
});

test('project file selection keeps removal and upload error recovery', async ({ page }) => {
    const routes = JSON.parse(process.env.VIEWER_BROWSER_ROUTES || '{}') as { project?: string };
    expect(routes.project, 'Run database-backed route cases through tests/browser/test_django_browser.py').toBeTruthy();
    await openController(page, `${routes.project!}upload/`, 'project-upload');
    await page.locator('#artifact').setInputFiles([
        { name: 'one.dmp', mimeType: 'application/octet-stream', buffer: Buffer.from('one') },
        { name: 'two.dmp', mimeType: 'application/octet-stream', buffer: Buffer.from('two') },
    ]);
    await expect(page.locator('.remove-file')).toHaveCount(2);
    await page.locator('.remove-file').first().click();
    await expect(page.locator('#dropzone')).not.toContainText('one.dmp');
    await expect(page.locator('#dropzone')).toContainText('two.dmp');
    await page.locator('#message').fill('Browser revision');
    const declaration = page.locator('[data-speleodb-controller="project-upload"]');
    const context = JSON.parse(await declaration.textContent() || '{}') as ProjectUploadContext;
    const url = new URL(getV2ProjectsUploadUrl(context.projectId, 'auto'), page.url()).href;
    await page.route(url, route => route.fulfill({ status: 400, json: { detail: 'Fixture upload rejected' } }));
    await page.locator('#btn_submit').click();
    await expect(page.locator('#modal_error_txt')).toContainText('Fixture upload rejected');
    await expect(page.locator('#loading_spinner')).toBeHidden();
    await expect(page.locator('#message')).toHaveValue('Browser revision');
    await expect(page.locator('#dropzone')).not.toContainText('one.dmp');
    await expect(page.locator('#dropzone')).toContainText('two.dmp');
});

test('survey table preserves native keyboard navigation and existing rows until clearing', async ({ page }) => {
    await openController(page, '/private/tools/xls_to_dmp/', 'xls2dmp');
    await page.locator('#clearBtn').click();
    await expect(page.locator('#dataTable tbody tr')).toHaveCount(0);
    await page.locator('#addRowBtn').click();
    const cells = page.locator('#dataTable tbody tr').first().locator('[contenteditable="true"]');
    await expect(cells).toHaveCount(7);
    await cells.first().fill('12');
    await cells.first().press('Tab');
    await expect(cells.nth(1)).toBeFocused();
    await page.locator('#addRowBtn').click();
    await expect(page.locator('#dataTable tbody tr')).toHaveCount(2);
    await expect(cells.first()).toHaveText('12');
    await page.locator('#clearBtn').click();
    await expect(page.locator('#dataTable tbody tr')).toHaveCount(0);
    await expect(page.locator('#status')).toHaveText('Cleared.');
});

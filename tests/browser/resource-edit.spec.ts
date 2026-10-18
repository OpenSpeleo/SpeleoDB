import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import type { StationResource } from '@speleodb/api';
import { BROWSER_TEST_BUDGETS } from './budgets.ts';
import { login } from './viewer-fixture.ts';

interface ResourceEditRecords { station: string; note: string; document: string }

async function openResources(page: Page, stationId: string) {
    await page.goto('/private/map_viewer/');
    const hideDebugToolbar = page.getByRole('link', { name: 'Hide »', exact: true });
    if (await hideDebugToolbar.isVisible()) await hideDebugToolbar.click();
    await expect(page.locator('#loading-overlay')).toBeHidden({ timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    await page.getByRole('button', { name: 'Managers', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Surface Stations', exact: true }).click();
    await page.locator(`#surface-station-manager-content div[data-station-id="${stationId}"]`).click();
    const modal = page.locator('#station-modal');
    await expect(modal).toBeVisible();
    await expect(modal.locator('#station-modal-title')).toContainText('Resource station');
    await modal.locator('[data-tab="resources"]').click();
    return modal;
}

test('the rendered resource edit form persists notes and replacement files without submitting its disabled type', async ({ page, browserName }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    const fixtures = JSON.parse(process.env.VIEWER_BROWSER_RESOURCE_RECORDS || '{}') as Record<string, ResourceEditRecords>;
    const records = fixtures[browserName];
    expect(records, 'Run through tests/browser/test_django_browser.py for isolated database and storage fixtures').toBeTruthy();
    if (!records) throw new Error('Missing resource edit records.');
    await login(page);
    const modal = await openResources(page, records.station);
    for (const kind of ['note', 'document'] as const) {
        const resourceId = records[kind];
        const resourcePath = `/api/v2/resources/${resourceId}/`;
        const before = await page.request.get(resourcePath);
        expect(before.status()).toBe(200);
        const original = await before.json() as StationResource;
        expect(original.title).toBe(`Original ${kind}`);
        await modal.locator(`.edit-resource-btn[data-resource-id="${resourceId}"]`).click();
        const form = modal.locator('#resource-edit-form');
        await expect(form.locator('[name="resource_type"]')).toBeDisabled();
        await form.locator('[name="title"]').fill(`Updated ${kind}`);
        await form.locator('[name="description"]').fill('');
        if (kind === 'note') {
            await form.locator('[name="text_content"]').fill('Updated note café 🦇');
        } else {
            await form.locator('[name="file"]').setInputFiles({
                name: 'replacement.txt', mimeType: 'text/plain', buffer: Buffer.from('Replacement café 🦇'),
            });
        }
        const submitted = page.waitForRequest(request => request.url().endsWith(resourcePath) && request.method() === 'PATCH');
        const saved = page.waitForResponse(response => response.url().endsWith(resourcePath) && response.request().method() === 'PATCH');
        await form.getByRole('button', { name: 'Save Changes' }).click();
        const request = await submitted;
        expect(request.headers()['content-type']).toMatch(/^multipart\/form-data; boundary=/);
        const response = await saved;
        expect(response.status(), await response.text()).toBe(200);
        // The Django wrapper checks the actual received multipart fields and
        // file bytes; browser debug protocols omit uploaded file contents.
        expect(response.headers()['x-speleodb-test-resource-patch']).toBe(resourcePath);
        await expect(form).toHaveCount(0);
        await expect(modal.locator('.resource-card').filter({ hasText: `Updated ${kind}` })).toHaveCount(1);

        // Independent real reads establish persisted values and actual S3 bytes.
        const read = await page.request.get(resourcePath);
        expect(read.status()).toBe(200);
        const persisted = await read.json() as StationResource;
        expect(persisted).toMatchObject({ title: `Updated ${kind}`, description: '', resource_type: kind });
        if (kind === 'note') {
            // The backend sanitizes text fields by removing accents before saving.
            expect(persisted.text_content).toBe('Updated note cafe 🦇');
        } else {
            expect(persisted.file).toBeTruthy();
            expect(persisted.file).not.toBe(original.file);
            const stored = await page.request.get(persisted.file!);
            expect(stored.status()).toBe(200);
            expect(await stored.text()).toBe('Replacement café 🦇');
        }
    }
    const reloaded = await openResources(page, records.station);
    for (const kind of ['note', 'document']) {
        await expect(reloaded.locator('.resource-card').filter({ hasText: `Updated ${kind}` })).toHaveCount(1);
    }
    expect(errors).toEqual([]);
});

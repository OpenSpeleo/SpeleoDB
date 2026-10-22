import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { installFixture, login } from './viewer-fixture.ts';

const network = {
    id: '70000000-0000-4000-8000-000000000001', name: 'Resource network',
    is_active: true, user_permission_level: 3, user_permission_level_label: 'ADMIN',
};
const station = {
    id: '70000000-0000-4000-8000-000000000002', name: 'Resource station',
    network: network.id, station_type: 'surface', latitude: 20, longitude: -87,
};
const resources = (['note', 'document'] as const).map((resource_type, index) => ({
    id: `70000000-0000-4000-8000-00000000000${index + 3}`, resource_type,
    title: `Original ${resource_type}`, description: 'Original description',
    text_content: resource_type === 'note' ? 'Original note text' : '',
    file: resource_type === 'document' ? '/viewer-fixtures/original.txt' : null,
    creation_date: '2026-01-01T12:00:00Z', created_by: 'Browser surveyor',
}));

async function openResources(page: Page) {
    await page.getByRole('button', { name: 'Managers', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Surface Stations', exact: true }).click();
    await page.locator(`#surface-station-manager-content div[data-station-id="${station.id}"]`).click();
    const modal = page.locator('#station-modal');
    await expect(modal).toBeVisible();
    await expect(modal.locator('#station-modal-title')).toContainText(station.name);
    await modal.locator('[data-tab="resources"]').click();
    return modal;
}

test('resource edit forms show fixed types, file previews, error recovery and completion', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await login(page);
    // Both edit records exist independently of any preceding successful write.
    const resourceList = `/api/v2/stations/${station.id}/resources/`;
    const apiResponses: Record<string, unknown> = {
        '/api/v2/surface-networks/': [network],
        '/api/v2/stations/surface/geojson/': { type: 'FeatureCollection', features: [{
            type: 'Feature', id: station.id, properties: station,
            geometry: { type: 'Point', coordinates: [station.longitude, station.latitude] },
        }] },
        [`/api/v2/stations/${station.id}/`]: station,
        [resourceList]: resources,
    };
    await installFixture(page, { emptyProjects: true, apiResponses });
    let fail = true;
    await page.route('**/api/v2/resources/**', async route => {
        const resource = resources.find(item => new URL(route.request().url()).pathname.endsWith(`/${item.id}/`));
        if (!resource) throw new Error('Unexpected resource edit fixture.');
        if (fail) {
            await route.fulfill({ status: 400, json: { detail: `The ${resource.resource_type} could not be saved. Try again.` } });
            return;
        }
        const updated = { ...resource, title: `Updated ${resource.resource_type}`, description: '' };
        apiResponses[resourceList] = resources.map(item => item.id === resource.id ? updated : item);
        await route.fulfill({ json: updated });
    });
    const modal = await openResources(page);
    for (const resource of resources) {
        fail = true;
        await modal.locator(`.edit-resource-btn[data-resource-id="${resource.id}"]`).click();
        const form = modal.locator('#resource-edit-form');
        await expect(form.locator('[name="resource_type"]')).toBeDisabled();
        await expect(form.locator('[name="resource_type"]')).toHaveValue(resource.resource_type);
        await expect(form.locator('[name="title"]')).toHaveValue(resource.title);
        await form.locator('[name="title"]').fill(`Updated ${resource.resource_type}`);
        await form.locator('[name="description"]').fill('');
        if (resource.resource_type === 'note') {
            await form.locator('[name="text_content"]').fill('Updated note café 🦇');
        } else {
            await expect(form).toContainText('Current file: original.txt');
            await form.locator('[name="file"]').setInputFiles({
                name: 'replacement.txt', mimeType: 'text/plain', buffer: Buffer.from('Replacement café 🦇'),
            });
            await expect(form.locator('#edit-file-container')).toContainText('replacement.txt');
        }
        const save = form.getByRole('button', { name: 'Save Changes' });
        await save.click();
        await expect(page.getByText(`The ${resource.resource_type} could not be saved. Try again.`, { exact: true }).last()).toBeVisible();
        await expect(form).toBeVisible();
        await expect(save).toBeEnabled();
        await expect(form.locator('[name="title"]')).toHaveValue(`Updated ${resource.resource_type}`);
        if (resource.resource_type === 'note') {
            await expect(form.locator('[name="text_content"]')).toHaveValue('Updated note café 🦇');
        } else {
            await expect(form.locator('#edit-file-container')).toContainText('replacement.txt');
        }
        fail = false;
        await save.click();
        await expect(form).toHaveCount(0);
        await expect(page.getByText('Resource updated successfully!', { exact: true }).last()).toBeVisible();
        await expect(modal.locator('.resource-card').filter({ hasText: `Updated ${resource.resource_type}` })).toHaveCount(1);
    }
    expect(errors).toEqual([]);
});

import { expect, test } from '@playwright/test';
import { expectRenderedFeatures, installFixture, login } from './viewer-fixture.ts';

interface BoundRecord {
    email: string;
    password: string;
    view_id: string;
    polygon_id: string;
    polygon_name: string;
    project_id: string;
    project_name: string;
    public_url: string;
    public_data_url: string;
    details_url: string;
}

test('Geographic Bound remains visible across map styles and its dashboard selector shows save feedback', async ({ page, browserName }) => {
    const records = JSON.parse(process.env.VIEWER_BROWSER_BOUND_RECORDS || '{}') as Record<string, BoundRecord>;
    const record = records[browserName];
    expect(record, 'Run through the real Django browser wrapper').toBeTruthy();
    const fixture = record!;
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    const project = {
        id: fixture.project_id, name: fixture.project_name, color: '#22c55e',
        geojson_file: '/bound-fixtures/survey.geojson',
    };
    // One inside segment is enough to exercise the real public composition.
    // Clipping coordinates, empty projects and source invariants belong to Vitest.
    await page.route('**/bound-fixtures/survey.geojson', route => route.fulfill({ json: {
        type: 'FeatureCollection', features: [{ type: 'Feature', properties: { depth: 10 }, geometry: {
            type: 'LineString', coordinates: [[-87.498, 20.105], [-87.492, 20.105]],
        } }],
    } }));
    await installFixture(page, { publicUrl: fixture.public_url, apiResponses: {
        [fixture.public_data_url]: {
            view_name: 'Browser bounded view', projects: [project], geographic_bound: {
                id: fixture.polygon_id, revision: 1, color: '#a855f7',
                geojson: { type: 'Polygon', coordinates: [[
                    [-87.5, 20.1], [-87.49, 20.1], [-87.49, 20.11], [-87.5, 20.11], [-87.5, 20.1],
                ]] },
            },
        },
    } });
    await page.getByRole('button', { name: 'Close modal', exact: true }).click();
    await expect(page.getByText(fixture.project_name, { exact: true })).toBeVisible();
    for (const suffix of ['fill', 'outline']) {
        await expectRenderedFeatures(page, `gis-geometry-${fixture.polygon_id}-${suffix}`, true);
    }
    await expect(page.locator('#create-geometry-btn, #map-managers-button')).toHaveCount(0);
    await page.getByRole('button', { name: 'Map Source', exact: true }).click();
    await page.locator('#map-source-menu input[type="radio"]:not(:checked)').first().locator('..').click();
    await expect(page.locator('#map-source-button')).not.toHaveAttribute('aria-busy', 'true');
    for (const suffix of ['fill', 'outline']) {
        await expectRenderedFeatures(page, `gis-geometry-${fixture.polygon_id}-${suffix}`, true);
    }

    // Editing starts from its own seeded record. Controlled responses exercise
    // feedback without making a browser responsible for persistence or payloads.
    await page.unroute('**/api/v2/**');
    await login(page, { email: fixture.email, password: fixture.password });
    await page.route('**/api/v2/projects/', route => route.fulfill({ json: [project] }));
    let fail = true;
    await page.route(`**/api/v2/user/gis_views/${fixture.view_id}/`, route => route.fulfill(fail
        ? { status: 400, json: { detail: 'The geographic bound could not be saved.' } }
        : { json: { id: fixture.view_id } }));
    await page.goto(fixture.details_url);
    const selector = page.getByLabel('Geographic Bound:', { exact: true });
    await expect(selector).toHaveValue(fixture.polygon_id);
    await expect(selector.locator('option:checked')).toHaveText(fixture.polygon_name);
    await selector.selectOption({ label: 'No geographic bound' });
    await expect(selector).toHaveValue('');
    await page.locator('#btn_submit').click();
    await expect(page.locator('#modal_error_txt')).toBeVisible();
    await expect(page.locator('#modal_error_txt')).toHaveText('The geographic bound could not be saved.');
    await page.locator('#modal_error').getByRole('button', { name: 'x Close', exact: true }).click();
    await expect(selector).toHaveValue('');
    fail = false;
    await page.locator('#btn_submit').click();
    await expect(page.locator('#modal_success_txt')).toBeVisible();
    await expect(page.locator('#modal_success_txt')).toHaveText('The GIS view has been updated successfully.');
    expect(errors).toEqual([]);
});

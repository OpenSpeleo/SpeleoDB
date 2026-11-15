import { expect, test } from '@playwright/test';
import { expectRenderedFeatures, installFixture, login, projectId, waitForViewerIdle } from './viewer-fixture.ts';

const leadId = '80000000-0000-4000-8000-000000000001';
const coordinates: [number, number] = [-86.998, 20.001];

test('exploration lead compass preserves independent directions through pointer capture and keyboard editing', async ({ page, browserName }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await login(page);
    await installFixture(page, { apiResponses: {
        '/api/v2/exploration-leads/geojson/': { type: 'FeatureCollection', features: [{
            type: 'Feature', id: leadId,
            geometry: { type: 'Point', coordinates },
            properties: {
                project: projectId(0), description: 'Three passages', headings: [0, 180, 270],
                created_by: 'Browser surveyor', creation_date: '2026-01-01T12:00:00Z',
                modified_date: '2026-01-01T12:00:00Z',
            },
        }] },
    } });
    await page.locator('#panel-toggle').click();
    await expectRenderedFeatures(page, 'exploration-leads-layer', true);
    await waitForViewerIdle(page);
    const point = await page.evaluate(value => window.__viewerEvidence.map.project(value), coordinates);
    await page.locator('canvas.maplibregl-canvas').click({ position: point });
    const modal = page.locator('#lead-details-modal');
    await expect(modal).toBeVisible();
    const compass = modal.locator('svg[aria-label="Exploration lead compass"]');
    await compass.scrollIntoViewIfNeeded();
    const dial = await compass.boundingBox();
    expect(dial).not.toBeNull();
    // Begin on the outer ring, clear of the numeric editor in the dial's center.
    await page.mouse.move(dial!.x + dial!.width / 2, dial!.y + dial!.height * 0.1);
    await page.mouse.down();
    // Move outside the SVG while holding the pointer, then return to due east.
    // Updating the selected heading during drag must retain capture on the dial.
    await page.mouse.move(dial!.x + dial!.width + 20, dial!.y + dial!.height / 2, { steps: 8 });
    await page.mouse.move(dial!.x + dial!.width * 0.9, dial!.y + dial!.height / 2, { steps: 8 });
    await page.mouse.up();
    const directionOne = modal.getByRole('spinbutton', { name: 'Direction 1 in degrees' });
    // Native mouse events can quantize fractional coordinates to a CSS pixel.
    // At this measured radius, that gives the integer readout a bounded angular resolution.
    const pointerToleranceDegrees = Math.ceil(Math.atan2(1, dial!.width * 0.4) * 180 / Math.PI);
    await expect.poll(async () => Math.abs(Number(await directionOne.inputValue()) - 90)).toBeLessThanOrEqual(pointerToleranceDegrees);
    const draggedHeading = await directionOne.inputValue();
    await modal.getByRole('tab', { name: 'Lead 2', exact: true }).click();
    await expect(modal.getByRole('spinbutton', { name: 'Direction 2 in degrees' })).toHaveValue('180');
    await page.keyboard.press('ArrowRight');
    await expect(modal.getByRole('tab', { name: 'Lead 3', exact: true })).toBeFocused();
    await expect(modal.getByRole('spinbutton', { name: 'Direction 3 in degrees' })).toHaveValue('270');

    const third = compass.locator('[data-heading-index="2"]');
    await expect(third).toBeVisible();
    await third.focus();
    await page.keyboard.press('ArrowRight');
    await expect(compass.locator('[data-heading-index="2"]')).toBeFocused();
    await expect(modal.getByRole('spinbutton', { name: 'Direction 3 in degrees' })).toHaveValue('271');
    await modal.getByRole('tab', { name: 'Lead 1', exact: true }).click();
    await expect(directionOne).toHaveValue(draggedHeading);

    if (browserName === 'chromium') {
        // Chromium exposes native multi-contact input. WebKit automation has no
        // equivalent, so its evidence above remains native mouse and keyboard.
        const cdp = await page.context().newCDPSession(page);
        try {
            await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: true });
            const center = { x: dial!.x + dial!.width / 2, y: dial!.y + dial!.height / 2 };
            const radius = dial!.width * 0.4;
            const firstTouch = { id: 1, x: center.x + radius, y: center.y };
            const otherTouch = { id: 2, x: center.x, y: center.y + radius };
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [firstTouch] });
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [firstTouch, otherTouch] });
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [
                { ...firstTouch, x: center.x + radius / Math.sqrt(2), y: center.y - radius / Math.sqrt(2) },
                { ...otherTouch, x: center.x - radius, y: center.y },
            ] });
            await expect.poll(async () => Number(await directionOne.inputValue())).toBeCloseTo(45, 0);
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchCancel', touchPoints: [] });
            // A cancelled gesture must release ownership so a new contact edits
            // the selected direction normally, without retaining the old pointer.
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [
                { id: 3, x: center.x, y: center.y - radius },
            ] });
            await expect(directionOne).toHaveValue('0');
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
            await modal.getByRole('tab', { name: 'Lead 2', exact: true }).click();
            await expect(modal.getByRole('spinbutton', { name: 'Direction 2 in degrees' })).toHaveValue('180');
            await modal.getByRole('tab', { name: 'Lead 3', exact: true }).click();
            await expect(modal.getByRole('spinbutton', { name: 'Direction 3 in degrees' })).toHaveValue('271');
        } finally {
            await cdp.detach();
        }
    }
    await modal.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(modal).toHaveCount(0);
    expect(errors).toEqual([]);
});

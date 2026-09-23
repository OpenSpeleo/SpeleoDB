import { writeFile } from 'node:fs/promises';
import { test, expect } from '@playwright/test';
import { gisId, installFixture, login, projectId, toggleLabel, trackId } from './viewer-fixture.mjs';

test.beforeEach(async ({ page }) => { await login(page); });

async function attachJSON(testInfo, name, data) {
    const path = testInfo.outputPath(name);
    await writeFile(path, JSON.stringify(data, null, 2));
    await testInfo.attach(name, { path, contentType: 'application/json' });
}

async function verifySettings(page, testInfo, stress) {
    const { requests } = await installFixture(page, { stress });
    await page.locator('#map-settings-button').click();
    const entrances = page.locator('[data-category="caveEntrances"]');
    const baseline = await page.evaluate(() => {
        const evidence = window.__viewerEvidence;
        evidence.traces = [];
        evidence.longTasks = [];
        return { sourceAdds: evidence.sourceAdds, sourceUpdates: evidence.sourceUpdates };
    });
    const downloads = new Map(requests);
    for (let iteration = 0; iteration < 12; iteration++) {
        await toggleLabel(entrances);
        await expect(page.locator('#map-settings-dialog')).not.toHaveAttribute('aria-busy', 'true');
    }
    await page.locator('input[name="map-settings-color-mode"][value="depth"]').locator('..').click();
    await expect(page.locator('#map-settings-dialog')).not.toHaveAttribute('aria-busy', 'true');
    await expect.poll(() => page.evaluate(() => window.__viewerEvidence.traces
        .filter(trace => Number.isFinite(trace.feedbackFrameMs)).length)).toBe(13);
    const evidence = await page.evaluate(() => {
        const { traces, sourceAdds, sourceUpdates, longTasks, map } = window.__viewerEvidence;
        return { traces, sourceAdds, sourceUpdates, longTasks, color: map.getPaintProperty(`project-layer-${'10000000-0000-4000-8000-000000000000'}`, 'line-color') };
    });
    expect(evidence.sourceAdds).toBe(baseline.sourceAdds);
    expect(evidence.sourceUpdates).toBe(baseline.sourceUpdates);
    expect(requests).toEqual(downloads);
    expect(evidence.color[2][0]).toBe('interpolate');
    expect(evidence.traces).toHaveLength(13);
    for (const trace of evidence.traces) {
        expect(trace.mutationsBeforeFrame).toBe(0);
        expect(trace.firstFrameChecked).toBe(trace.checked);
    }
    const durations = evidence.traces.map(trace => trace.feedbackFrameMs).sort((a, b) => a - b);
    const p95 = durations[Math.ceil(durations.length * .95) - 1];
    await attachJSON(testInfo, 'viewer-latency.json', { p95FeedbackFrameMs: p95, ...evidence });
    expect(p95).toBeLessThanOrEqual(100);
    await expect(page.locator('canvas.mapboxgl-canvas')).toBeVisible();
}

test('settings acknowledge intent before rendering and display changes reuse 120,000 survey segments', async ({ page }, testInfo) => {
    await verifySettings(page, testInfo, true);
});

test('settings baseline acknowledges intent and reuses 4,000 survey segments', async ({ page }, testInfo) => {
    await verifySettings(page, testInfo, false);
});

test('a second GPS toggle stays available during loading and final intent wins without duplicate downloads', async ({ page }, testInfo) => {
    const { gates, requests } = await installFixture(page);
    let release;
    gates.set('/viewer-fixtures/track.geojson', new Promise(resolve => { release = resolve; }));
    await page.locator('#gps-panel-expand').click();
    const input = page.getByLabel('Show Large GPS track', { exact: true });
    await toggleLabel(input);
    await expect(input).toBeChecked();
    await expect.poll(() => requests.get('/viewer-fixtures/track.geojson') || 0).toBe(1);
    await expect(input).toBeEnabled();
    await toggleLabel(input);
    await expect(input).not.toBeChecked();
    await toggleLabel(input);
    await expect(input).toBeChecked();
    await page.evaluate(id => {
        const evidence = window.__viewerEvidence;
        evidence.traces = [];
        evidence.preparationGaps = [];
        let last = performance.now();
        evidence.preparationTimer = setInterval(() => {
            const now = performance.now();
            if (evidence.map.getSource(`gps-track-source-${id}`)) {
                clearInterval(evidence.preparationTimer);
                return;
            }
            evidence.preparationGaps.push(now - last);
            last = now;
        }, 0);
    }, trackId);
    release();
    // The large single feature is now being parsed/transferred/prepared, rather
    // than merely waiting for its network response.
    await expect.poll(() => page.evaluate(() => window.__viewerEvidence.workerMessages)).toBeGreaterThan(1);
    expect(await page.evaluate(id => Boolean(window.__viewerEvidence.map.getSource(`gps-track-source-${id}`)), trackId)).toBe(false);
    await toggleLabel(input);
    await expect(input).not.toBeChecked();
    await toggleLabel(input);
    await expect(input).toBeChecked();
    await expect.poll(() => page.evaluate(id => window.__viewerEvidence.map.getLayoutProperty(`gps-track-line-${id}`, 'visibility'), trackId)).toBe('visible');
    await expect.poll(() => page.evaluate(() => window.__viewerEvidence.traces
        .filter(trace => Number.isFinite(trace.feedbackFrameMs)).length)).toBe(2);
    const preparation = await page.evaluate(() => ({
        gaps: window.__viewerEvidence.preparationGaps,
        traces: window.__viewerEvidence.traces,
        messages: window.__viewerEvidence.workerMessages,
    }));
    await attachJSON(testInfo, 'single-feature-preparation.json', preparation);
    expect(preparation.messages).toBeGreaterThan(2);
    expect(preparation.traces).toHaveLength(2);
    expect(requests.get('/viewer-fixtures/track.geojson')).toBe(1);
    await toggleLabel(input);
    await expect.poll(() => page.evaluate(id => window.__viewerEvidence.map.getLayoutProperty(`gps-track-line-${id}`, 'visibility'), trackId)).toBe('none');
    await testInfo.attach('gps-final-state.png', { body: await page.screenshot(), contentType: 'image/png' });
    expect(Math.max(...preparation.gaps)).toBeLessThanOrEqual(50);
    for (const trace of preparation.traces) expect(trace.feedbackFrameMs).toBeLessThanOrEqual(100);
});

test('GIS load failure permits retry and mixed geometry toggles preserve sources', async ({ page }) => {
    const { failures, requests } = await installFixture(page);
    failures.add('/viewer-fixtures/gis.geojson');
    await page.locator('#gis-panel-expand').click();
    const input = page.getByLabel('Show Mixed GIS layer', { exact: true });
    await toggleLabel(input);
    await expect(input).not.toBeChecked();
    await expect(input).toBeEnabled();
    failures.delete('/viewer-fixtures/gis.geojson');
    await toggleLabel(input);
    await expect.poll(() => page.evaluate(id => Boolean(window.__viewerEvidence.map.getSource(`gis-layer-source-${id}`)), gisId)).toBe(true);
    const polygon = page.getByLabel('Show Polygon in Mixed GIS layer', { exact: true });
    const before = await page.evaluate(() => window.__viewerEvidence.sourceUpdates);
    await toggleLabel(polygon);
    await expect(polygon).not.toBeChecked();
    await expect.poll(() => page.evaluate(id => window.__viewerEvidence.map.getFilter(`gis-layer-${id}-fill`)[2][2][1], gisId)).not.toContain('Polygon');
    expect(await page.evaluate(() => window.__viewerEvidence.sourceUpdates)).toBe(before);
    expect(requests.get('/viewer-fixtures/gis.geojson')).toBe(2);
    expect(await page.evaluate(id => window.__viewerEvidence.map.getLayoutProperty(`project-layer-${id}`, 'visibility'), projectId(0))).toBe('visible');
});

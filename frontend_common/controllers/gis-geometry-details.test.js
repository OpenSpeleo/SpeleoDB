import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { init, parseGeometryText } from './gis-geometry-details.js';
import { DEFAULTS } from '../../frontend_private/static/private/js/map_viewer/config.js';

vi.mock('../readiness.js', () => ({ afterWindowLoad: () => Promise.resolve() }));

const jquery = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '../../frontend_public/static/js/vendors/jquery-3.7.1.js'), 'utf8');
const geometry = { type: 'LineString', coordinates: [[-87, 20], [-87.001, 20.001]] };
let dispose;

beforeAll(() => {
    // Match the application-owned jQuery dependency used by shared forms.
    (0, eval)(jquery);
});

beforeEach(() => {
    document.body.innerHTML = `
        <form id="geometry-form">
            <fieldset><input name="csrfmiddlewaretoken" value="token">
                <input name="name" value="Boundary">
                <input name="color" id="color-value" value="#123456">
                <input id="color-hex-input" value="123456">
                <input type="color" id="color-picker" value="#123456">
                <span id="color-preview"></span>
                <button type="button" class="color-preset" data-color="#abcdef">Color</button>
            </fieldset>
            <textarea id="geometry-geojson"></textarea>
            <span id="geometry-summary"></span><span id="geometry-json-status"></span>
            <p id="geometry-error" hidden></p><p id="geometry-saved" hidden></p>
            <button id="btn_submit" type="submit">Save Changes</button>
        </form>`;
    document.getElementById('geometry-geojson').value = JSON.stringify(geometry, null, 2);
    vi.spyOn(globalThis.jQuery, 'ajax').mockImplementation(() => {});
});
afterEach(() => {
    dispose?.();
    dispose = undefined;
    vi.restoreAllMocks();
});

async function start(canWrite = true) {
    dispose = await init({ formId: 'geometry-form', endpoint: '/geometry/', revision: 3, canWrite });
}

function setField(selector, value) {
    const field = document.querySelector(selector);
    field.value = value;
    field.dispatchEvent(new Event('input', { bubbles: true }));
}

function submit() {
    document.getElementById('geometry-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
}

describe('GIS Geometry atomic settings form', () => {
    it('rejects invalid raw JSON without submitting edited metadata or losing text', async () => {
        await start();
        setField('[name="name"]', 'Renamed');
        setField('#geometry-geojson', '{ incomplete');
        submit();
        expect(globalThis.jQuery.ajax).not.toHaveBeenCalled();
        expect(document.getElementById('geometry-geojson').value).toBe('{ incomplete');
        expect(document.querySelector('[name="name"]').value).toBe('Renamed');
        expect(document.getElementById('btn_submit').disabled).toBe(true);
        expect(document.getElementById('geometry-error').textContent).toContain('valid JSON');
    });

    it('sends metadata-only edits with revision, omitting unchanged geometry', async () => {
        await start();
        setField('[name="name"]', '  Renamed  ');
        submit();
        const request = globalThis.jQuery.ajax.mock.calls[0][0];
        expect(request.method).toBe('PATCH');
        expect(JSON.parse(request.data)).toEqual({ name: 'Renamed', color: '#123456', expected_revision: 3 });
        expect(document.getElementById('btn_submit').disabled).toBe(true);
        submit();
        expect(globalThis.jQuery.ajax).toHaveBeenCalledTimes(1);
    });

    it('saves name, color and GeoJSON atomically then uses the returned revision', async () => {
        await start();
        const changedGeometry = { type: 'LineString', coordinates: [[-87.1, 20.1], [-87.101, 20.101]] };
        setField('#geometry-geojson', JSON.stringify(changedGeometry));
        document.querySelector('.color-preset').click();
        submit();
        const request = globalThis.jQuery.ajax.mock.calls[0][0];
        expect(JSON.parse(request.data)).toEqual({ name: 'Boundary', color: '#abcdef', geojson: changedGeometry, expected_revision: 3 });
        request.success({ name: 'Boundary', color: '#abcdef', geojson: changedGeometry, revision: 4 });
        request.complete();
        expect(document.getElementById('btn_submit').disabled).toBe(true);
        expect(document.getElementById('geometry-saved').hidden).toBe(false);
        setField('[name="name"]', 'Next edit');
        submit();
        expect(JSON.parse(globalThis.jQuery.ajax.mock.calls[1][0].data).expected_revision).toBe(4);
    });

    it.each([0, 400, 409])('preserves edits after failed save (%s)', async status => {
        await start();
        setField('[name="name"]', 'Keep this name');
        submit();
        const request = globalThis.jQuery.ajax.mock.calls[0][0];
        request.error({ status, responseJSON: { errors: { geojson: ['Geometry is invalid.'] } } });
        request.complete();
        expect(document.querySelector('[name="name"]').value).toBe('Keep this name');
        expect(document.getElementById('geometry-geojson').value).toBe(JSON.stringify(geometry, null, 2));
        expect(document.getElementById('geometry-error').hidden).toBe(false);
        expect(document.getElementById('btn_submit').disabled).toBe(false);
    });

    it('locks saving after permission loss while retaining draft fields', async () => {
        await start();
        setField('[name="name"]', 'Keep this name');
        submit();
        const request = globalThis.jQuery.ajax.mock.calls[0][0];
        request.error({ status: 403 });
        request.complete();
        expect(document.getElementById('btn_submit').disabled).toBe(true);
        expect(document.getElementById('geometry-error').textContent).toContain('no longer have permission');
        expect(document.querySelector('[name="name"]').value).toBe('Keep this name');
    });

    it('does not silently save the previous color when the visible hex field is incomplete', async () => {
        await start();
        setField('[name="name"]', 'New name');
        setField('#color-hex-input', '12');
        submit();
        expect(globalThis.jQuery.ajax).not.toHaveBeenCalled();
        expect(document.getElementById('btn_submit').disabled).toBe(true);
        expect(document.getElementById('geometry-error').textContent).toContain('six-digit');
    });

    it('does not wire mutations for read-only viewers', async () => {
        await start(false);
        setField('[name="name"]', 'Forbidden');
        submit();
        expect(globalThis.jQuery.ajax).not.toHaveBeenCalled();
        expect(document.getElementById('geometry-summary').textContent).toContain('LineString');
    });

    it('warns above the warning threshold while allowing a shape below the shared maximum', async () => {
        await start();
        setField('#geometry-geojson', JSON.stringify({ type: 'LineString', coordinates: [[0, 0], [0.04, 0.04]] }));
        const summary = document.getElementById('geometry-summary');
        const maximumArea = DEFAULTS.GIS_GEOMETRY.MAX_AREA_M2 / DEFAULTS.GIS_GEOMETRY.SQUARE_METRES_PER_SQUARE_KILOMETRE;
        expect(summary.classList.contains('geometry-details__summary--warning')).toBe(true);
        expect(summary.textContent).toContain(`${maximumArea.toLocaleString()} km² maximum`);
        expect(document.getElementById('btn_submit').disabled).toBe(false);
    });

    it('uses shared validation for shape, holes, vertex count, and bounding-box size', () => {
        expect(parseGeometryText('null').valid).toBe(false);
        expect(parseGeometryText(JSON.stringify({ type: 'Point', coordinates: [-87, 20] })).valid).toBe(false);
        expect(parseGeometryText(JSON.stringify({ type: 'FeatureCollection', features: [] })).valid).toBe(false);
        expect(parseGeometryText(JSON.stringify({ type: 'LineString', coordinates: Array.from({ length: 101 }, (_, index) => [index / 10000, 0]) })).valid).toBe(false);
        expect(parseGeometryText(JSON.stringify({ type: 'LineString', coordinates: [[0, 0], [1, 1]] })).valid).toBe(false);
    });
});

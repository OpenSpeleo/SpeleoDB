import type { GISGeometryDetailsContext } from '../../ts-types/controllers/gis-geometry-details.ts';
import type { FormTestJQuery } from '../../ts-types/testing/vitest/forms.ts';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { init as initialize, parseGeometryText } from './gis-geometry-details.ts';
import { DEFAULTS } from '../../frontend_private/static/private/ts/map_viewer/config.ts';

vi.mock('../readiness.ts', () => ({ afterWindowLoad: () => Promise.resolve() }));

const jquery = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '../../frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const geometry = { type: 'LineString', coordinates: [[-87, 20], [-87.001, 20.001]] };
let dispose: (() => void) | undefined;
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };
function init(context?: unknown) { return initialize(context as GISGeometryDetailsContext); }
function element<T extends HTMLElement = HTMLElement>(id: string) { return document.getElementById(id) as T; }

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
    element<HTMLTextAreaElement>('geometry-geojson').value = JSON.stringify(geometry, null, 2);
    vi.spyOn(jqueryHost.jQuery, 'ajax').mockImplementation(() => {});
});
afterEach(() => {
    dispose?.();
    dispose = undefined;
    vi.restoreAllMocks();
});

async function start(canWrite = true) {
    dispose = await init({ formId: 'geometry-form', endpoint: '/geometry/', revision: 3, canWrite });
}

function setField(selector: string, value: string) {
    const field = document.querySelector<HTMLInputElement>(selector)!;
    field.value = value;
    field.dispatchEvent(new Event('input', { bubbles: true }));
}

function submit() {
    element<HTMLElement>('geometry-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
}

describe('GIS Geometry atomic settings form', () => {
    it('returns without wiring when the form or textarea is absent, but retains required-field failures', async () => {
        element<HTMLElement>('geometry-form').remove();
        await expect(init({ formId: 'geometry-form' })).resolves.toBeUndefined();
        document.body.innerHTML = '<form id="geometry-form"><textarea id="geometry-geojson"></textarea></form>';
        await expect(init({ formId: 'geometry-form' })).rejects.toThrow(TypeError);
        await expect(init()).rejects.toThrow(TypeError);
    });

    it('returns a cleanup for its unload listener and independently attaches repeated initialization', async () => {
        const add = vi.spyOn(window, 'addEventListener');
        const remove = vi.spyOn(window, 'removeEventListener');
        const first = await init({ formId: 'geometry-form', endpoint: '/geometry/', revision: 3, canWrite: true });
        await start();
        expect(add.mock.calls.filter(([name]) => name === 'beforeunload')).toHaveLength(2);
        first!();
        expect(remove).toHaveBeenCalledWith('beforeunload', add.mock.calls.find(([name]) => name === 'beforeunload')![1]);
        setField('[name="name"]', 'Repeated');
        submit();
        expect(jqueryHost.jQuery.ajax).toHaveBeenCalledTimes(2);
    });

    it('rejects invalid raw JSON without submitting edited metadata or losing text', async () => {
        await start();
        setField('[name="name"]', 'Renamed');
        setField('#geometry-geojson', '{ incomplete');
        submit();
        expect(jqueryHost.jQuery.ajax).not.toHaveBeenCalled();
        expect(element<HTMLTextAreaElement>('geometry-geojson').value).toBe('{ incomplete');
        expect(document.querySelector<HTMLInputElement>('[name="name"]')!.value).toBe('Renamed');
        expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(true);
        expect(element<HTMLElement>('geometry-error').textContent).toContain('valid JSON');
    });

    it('sends metadata-only edits with revision, omitting unchanged geometry', async () => {
        await start();
        setField('[name="name"]', '  Renamed  ');
        submit();
        const request = jqueryHost.jQuery.ajax.mock.calls[0]![0];
        expect(request.method).toBe('PATCH');
        expect(JSON.parse(request.data!)).toEqual({ name: 'Renamed', color: '#123456', expected_revision: 3 });
        expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(true);
        submit();
        expect(jqueryHost.jQuery.ajax).toHaveBeenCalledTimes(1);
    });

    it('saves name, color and GeoJSON atomically then uses the returned revision', async () => {
        await start();
        const changedGeometry = { type: 'LineString', coordinates: [[-87.1, 20.1], [-87.101, 20.101]] };
        setField('#geometry-geojson', JSON.stringify(changedGeometry));
        document.querySelector<HTMLButtonElement>('.color-preset')!.click();
        submit();
        const request = jqueryHost.jQuery.ajax.mock.calls[0]![0];
        expect(JSON.parse(request.data!)).toEqual({ name: 'Boundary', color: '#abcdef', geojson: changedGeometry, expected_revision: 3 });
        request.success({ name: 'Boundary', color: '#abcdef', geojson: changedGeometry, revision: 4 });
        request.complete!();
        expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(true);
        expect(element<HTMLElement>('geometry-saved').hidden).toBe(false);
        setField('[name="name"]', 'Next edit');
        submit();
        expect(JSON.parse(jqueryHost.jQuery.ajax.mock.calls[1]![0].data!)).toMatchObject({ expected_revision: 4 });
    });

    it.each([0, 400, 409])('preserves edits after failed save (%s)', async status => {
        await start();
        setField('[name="name"]', 'Keep this name');
        submit();
        const request = jqueryHost.jQuery.ajax.mock.calls[0]![0];
        request.error({ status, responseJSON: { errors: { geojson: ['Geometry is invalid.'] } } });
        request.complete!();
        expect(document.querySelector<HTMLInputElement>('[name="name"]')!.value).toBe('Keep this name');
        expect(element<HTMLTextAreaElement>('geometry-geojson').value).toBe(JSON.stringify(geometry, null, 2));
        expect(element<HTMLElement>('geometry-error').hidden).toBe(false);
        expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(false);
    });

    it('locks saving after permission loss while retaining draft fields', async () => {
        await start();
        setField('[name="name"]', 'Keep this name');
        submit();
        const request = jqueryHost.jQuery.ajax.mock.calls[0]![0];
        request.error({ status: 403 });
        request.complete!();
        expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(true);
        expect(element<HTMLElement>('geometry-error').textContent).toContain('no longer have permission');
        expect(document.querySelector<HTMLInputElement>('[name="name"]')!.value).toBe('Keep this name');
    });

    it('does not silently save the previous color when the visible hex field is incomplete', async () => {
        await start();
        setField('[name="name"]', 'New name');
        setField('#color-hex-input', '12');
        submit();
        expect(jqueryHost.jQuery.ajax).not.toHaveBeenCalled();
        expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(true);
        expect(element<HTMLElement>('geometry-error').textContent).toContain('six-digit');
    });

    it('does not wire mutations for read-only viewers', async () => {
        await start(false);
        setField('[name="name"]', 'Forbidden');
        submit();
        expect(jqueryHost.jQuery.ajax).not.toHaveBeenCalled();
        expect(element<HTMLElement>('geometry-summary').textContent).toContain('LineString');
    });

    it('warns above the warning threshold while allowing a shape below the shared maximum', async () => {
        await start();
        setField('#geometry-geojson', JSON.stringify({ type: 'LineString', coordinates: [[0, 0], [0.04, 0.04]] }));
        const summary = element<HTMLElement>('geometry-summary');
        const maximumArea = DEFAULTS.GIS_GEOMETRY.MAX_AREA_M2 / DEFAULTS.GIS_GEOMETRY.SQUARE_METRES_PER_SQUARE_KILOMETRE;
        expect(summary.classList.contains('geometry-details__summary--warning')).toBe(true);
        expect(summary.textContent).toContain(`${maximumArea.toLocaleString()} km² maximum`);
        expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(false);
    });

    it('uses shared validation for shape, holes, vertex count, and bounding-box size', () => {
        expect(parseGeometryText('null').valid).toBe(false);
        expect(parseGeometryText(JSON.stringify({ type: 'Point', coordinates: [-87, 20] })).valid).toBe(false);
        expect(parseGeometryText(JSON.stringify({ type: 'FeatureCollection', features: [] })).valid).toBe(false);
        expect(parseGeometryText(JSON.stringify({ type: 'LineString', coordinates: Array.from({ length: 101 }, (_, index) => [index / 10000, 0]) })).valid).toBe(false);
        expect(parseGeometryText(JSON.stringify({ type: 'LineString', coordinates: [[0, 0], [1, 1]] })).valid).toBe(false);
    });
});

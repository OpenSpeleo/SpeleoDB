import { init, parseGeometryText } from './gis-geometry-details.ts';
import { DEFAULTS } from '../../frontend_private/static/private/ts/map_viewer/config.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

const geometry = { type: 'LineString', coordinates: [[-87, 20], [-87.001, 20.001]] };
let dispose: (() => void) | undefined;
function element<T extends HTMLElement = HTMLElement>(id: string) { return document.getElementById(id) as T; }
beforeEach(() => {
    document.body.innerHTML = `
        <form id="geometry-form">
            <fieldset><input name="csrfmiddlewaretoken" value="token">
                <input name="name" value="Boundary">
                <input name="alias" value="">
                <textarea name="description"></textarea>
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

    server.reply({ json: { name: 'Boundary', alias: '', description: '', color: '#123456', geojson: geometry, revision: 4 } });
});
afterEach(() => { dispose?.(); dispose = undefined; $(document).off(); $('body').off(); document.body.innerHTML = ''; });
async function start(canWrite = true) { dispose = await init({ formId: 'geometry-form', geometryId: 'geometry', revision: 3, canWrite }); }
function setField(selector: string, value: string) { const field = document.querySelector<HTMLInputElement>(selector)!; field.value = value; field.dispatchEvent(new Event('input', { bubbles: true })); }
function submit() { element('geometry-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); }

it('rejects invalid JSON and incomplete color without losing edited fields', async () => {
    await start(); setField('[name=name]', 'Renamed'); setField('#geometry-geojson', '{ incomplete'); submit();
    expect(server.requests).toHaveLength(0); expect(element<HTMLTextAreaElement>('geometry-geojson').value).toBe('{ incomplete');
    expect(element('geometry-error').textContent).toContain('valid JSON');
    setField('#geometry-geojson', JSON.stringify(geometry)); setField('#color-hex-input', '12'); submit();
    expect(server.requests).toHaveLength(0); expect(element('geometry-error').textContent).toContain('six-digit');
});

it('sends metadata-only changes with revision and blocks duplicate submissions while pending', async () => {
    let finish!: () => void;
    server.handle(() => new Promise(resolve => { finish = () => resolve({ json: { name: 'Renamed', alias: '', description: '', color: '#123456', geojson: geometry, revision: 4 } }); }));
    await start(); setField('[name=name]', '  Renamed  '); submit();
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    expect(server.requests[0]).toMatchObject({ method: 'PATCH', path: '/api/v2/gis-geometries/geometry/' });
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ name: 'Renamed', alias: '', description: '', color: '#123456', expected_revision: 3 });
    expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(true); submit();
    await Promise.resolve(); expect(server.requests).toHaveLength(1); finish();
    await vi.waitFor(() => expect(element('geometry-saved').hidden).toBe(false));
});

it('saves metadata and geometry atomically and adopts the returned revision for the next request', async () => {
    const changed = { type: 'LineString', coordinates: [[-87.1, 20.1], [-87.101, 20.101]] };
    server.reply({ json: { name: 'Boundary', alias: '', description: '', color: '#abcdef', geojson: changed, revision: 4 } });
    await start(); setField('#geometry-geojson', JSON.stringify(changed)); document.querySelector<HTMLButtonElement>('.color-preset')!.click(); submit();
    await vi.waitFor(() => expect(element('geometry-saved').hidden).toBe(false));
    expect(JSON.parse(server.requests[0]!.body)).toEqual({ name: 'Boundary', alias: '', description: '', color: '#abcdef', geojson: changed, expected_revision: 3 });
    setField('[name=name]', 'Next'); submit(); await vi.waitFor(() => expect(server.requests).toHaveLength(2));
    expect(JSON.parse(server.requests[1]!.body)).toMatchObject({ expected_revision: 4 });
});

it.each([400, 409, 503])('preserves draft edits after HTTP %s and enables retry', async status => {
    server.reply({ status, json: { errors: { geojson: ['Geometry is invalid.'] } } });
    await start(); setField('[name=name]', 'Keep'); submit();
    await vi.waitFor(() => expect(element('geometry-error').hidden).toBe(false));
    expect(document.querySelector<HTMLInputElement>('[name=name]')!.value).toBe('Keep');
    expect(element<HTMLTextAreaElement>('geometry-geojson').value).toBe(JSON.stringify(geometry, null, 2));
    expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(false);
});

it('locks saving after permission loss while retaining the draft', async () => {
    server.reply({ status: 403, json: { detail: 'Denied' } }); await start(); setField('[name=name]', 'Keep'); submit();
    await vi.waitFor(() => expect(element('geometry-error').textContent).toContain('no longer have permission'));
    expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(true); expect(document.querySelector<HTMLInputElement>('[name=name]')!.value).toBe('Keep');
});

it('does not wire mutations for read-only viewers', async () => {
    await start(false); setField('[name=name]', 'Forbidden'); submit(); expect(server.requests).toHaveLength(0);
    expect(element('geometry-summary').textContent).toContain('LineString');
});

it('preserves Unicode metadata limits and sends alias and description independently', async () => {
    await start(); setField('[name=alias]', '🦇'.repeat(33)); expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(true);
    setField('[name=alias]', '🦇'.repeat(32)); setField('[name=description]', 'Line one\nLine two'); submit();
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    expect(JSON.parse(server.requests[0]!.body)).toMatchObject({ alias: '🦇'.repeat(32), description: 'Line one\nLine two', expected_revision: 3 });
});

it('uses shared shape, vertex and bounding-box validation', async () => {
    for (const value of [null, { type: 'Point', coordinates: [-87, 20] }, { type: 'FeatureCollection', features: [] }, { type: 'LineString', coordinates: Array.from({ length: 101 }, (_, index) => [index / 10000, 0]) }, { type: 'LineString', coordinates: [[0, 0], [1, 1]] }]) expect(parseGeometryText(JSON.stringify(value)).valid).toBe(false);
    await start(); setField('#geometry-geojson', JSON.stringify({ type: 'LineString', coordinates: [[0, 0], [0.04, 0.04]] }));
    const maximum = DEFAULTS.GIS_GEOMETRY.MAX_AREA_M2 / DEFAULTS.GIS_GEOMETRY.SQUARE_METRES_PER_SQUARE_KILOMETRE;
    expect(element('geometry-summary').textContent).toContain(`${maximum.toLocaleString()} km² maximum`);
    expect(element<HTMLButtonElement>('btn_submit').disabled).toBe(false);
});

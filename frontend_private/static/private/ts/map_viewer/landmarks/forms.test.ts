import { startApiServer, setBrowserUrl } from '../../../../../../frontend_common/test/api-server.ts';
import {
    LandmarkForms, openLandmarkCreateModal, openLandmarkEditModal, openLandmarkDeleteModal,
    openLandmarkBulkDeleteModal,
    openLandmarkBulkTransferModal,
    renderLandmarkFormHtml,
    readLandmarkFormPayload,
    validateLandmarkFormPayload,
} from './forms.ts';
import * as landmarkModel from './form_model.ts';
import * as landmarkPresentation from './form_presentation.ts';

const VALID_CSRF_TOKEN = 'c'.repeat(64);

describe('renderLandmarkFormHtml', () => {
    it('keeps extracted model and presentation functions as the facade aliases', () => {
        expect(readLandmarkFormPayload).toBe(landmarkModel.readLandmarkFormPayload);
        expect(validateLandmarkFormPayload).toBe(landmarkModel.validateLandmarkFormPayload);
        expect(renderLandmarkFormHtml).toBe(landmarkPresentation.renderLandmarkFormHtml);
        expect(LandmarkForms.readLandmarkFormPayload).toBe(readLandmarkFormPayload);
        expect(LandmarkForms.validateLandmarkFormPayload).toBe(validateLandmarkFormPayload);
        expect(LandmarkForms.renderLandmarkFormHtml).toBe(renderLandmarkFormHtml);
    });
    it('renders create-mode form with empty fields', () => {
        const html = renderLandmarkFormHtml({
            mode: 'create',
            formId: 'lm-form',
            errorElId: 'lm-err',
        });

        expect(html).toContain('id="lm-form"');
        expect(html).toContain('id="lm-form-name"');
        expect(html).toContain('id="lm-form-latitude"');
        expect(html).toContain('id="lm-form-longitude"');
        expect(html).toContain('id="lm-err"');
    });

    it('renders edit-mode form with pre-filled values', () => {
        const landmark = {
            name: 'Cave Entrance',
            description: 'Main entrance',
            latitude: 45.123,
            longitude: -122.456,
            collection: 'col-1',
        };
        const html = renderLandmarkFormHtml({
            mode: 'edit',
            landmark,
            formId: 'edit-form',
            errorElId: 'edit-err',
        });

        expect(html).toContain('Cave Entrance');
        expect(html).toContain('Main entrance');
        expect(html).toContain('45.1230000');
        expect(html).toContain('-122.4560000');
    });

    it('escapes XSS in landmark name', () => {
        const landmark = {
            name: '<script>alert("xss")</script>',
            description: '',
            latitude: 0,
            longitude: 0,
        };
        const html = renderLandmarkFormHtml({
            mode: 'edit',
            landmark,
            formId: 'xss-form',
            errorElId: 'xss-err',
        });

        expect(html).not.toContain('<script>alert("xss")</script>');
        expect(html).toContain('&lt;script&gt;');
    });

    it('renders locked collection badge when lockedCollectionId is set', () => {
        const collections = [
            { id: 'c1', name: 'My Collection', color: '#ff0000', can_write: true },
        ];
        const html = renderLandmarkFormHtml({
            mode: 'create',
            collections,
            lockedCollectionId: 'c1',
            formId: 'locked-form',
            errorElId: 'locked-err',
        });

        expect(html).toContain('My Collection');
        expect(html).toContain('type="hidden"');
    });

    it('renders collection dropdown when no locked collection', () => {
        const collections = [
            { id: 'c1', name: 'Collection A', can_write: true },
            { id: 'c2', name: 'Collection B', can_write: true },
        ];
        const html = renderLandmarkFormHtml({
            mode: 'create',
            collections,
            formId: 'dd-form',
            errorElId: 'dd-err',
        });

        expect(html).toContain('<select');
        expect(html).toContain('Collection A');
        expect(html).toContain('Collection B');
    });
});

describe('readLandmarkFormPayload', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    it('reads form values from DOM elements', () => {
        document.body.innerHTML = `
            <form id="f"><input type="radio" name="icon" value="CAVE" checked></form>
            <input id="f-name" value="Test LM">
            <textarea id="f-description">A description</textarea>
            <input id="f-latitude" value="45.5">
            <input id="f-longitude" value="-122.5">
            <select id="f-collection"><option value="col-1" selected>Col</option></select>
        `;
        const payload = readLandmarkFormPayload('f', null);

        expect(payload.name).toBe('Test LM');
        expect(payload.description).toBe('A description');
        expect(payload.latitude).toBe(45.5);
        expect(payload.longitude).toBe(-122.5);
        expect(payload.collection).toBe('col-1');
    });

    it('uses lockedCollectionId when provided', () => {
        document.body.innerHTML = `
            <form id="f"><input type="radio" name="icon" value="CAVE" checked></form>
            <input id="f-name" value="Test">
            <textarea id="f-description"></textarea>
            <input id="f-latitude" value="10">
            <input id="f-longitude" value="20">
            <input id="f-collection" type="hidden" value="ignored">
        `;
        const payload = readLandmarkFormPayload('f', 'locked-col');

        expect(payload.collection).toBe('locked-col');
    });
});

describe('validateLandmarkFormPayload', () => {
    it('returns null for valid payload', () => {
        const result = validateLandmarkFormPayload({
            name: 'Valid',
            latitude: 45.0,
            longitude: -122.0,
        });
        expect(result).toBeNull();
    });

    it('rejects empty name', () => {
        const result = validateLandmarkFormPayload({
            name: '',
            latitude: 45.0,
            longitude: -122.0,
        });
        expect(result).toContain('name');
    });

    it('rejects latitude > 90', () => {
        const result = validateLandmarkFormPayload({
            name: 'Test',
            latitude: 91,
            longitude: 0,
        });
        expect(result).toContain('Latitude');
    });

    it('rejects latitude < -90', () => {
        const result = validateLandmarkFormPayload({
            name: 'Test',
            latitude: -91,
            longitude: 0,
        });
        expect(result).toContain('Latitude');
    });

    it('rejects longitude > 180', () => {
        const result = validateLandmarkFormPayload({
            name: 'Test',
            latitude: 0,
            longitude: 181,
        });
        expect(result).toContain('Longitude');
    });

    it('rejects longitude < -180', () => {
        const result = validateLandmarkFormPayload({
            name: 'Test',
            latitude: 0,
            longitude: -181,
        });
        expect(result).toContain('Longitude');
    });

    it('rejects NaN latitude', () => {
        const result = validateLandmarkFormPayload({
            name: 'Test',
            latitude: NaN,
            longitude: 0,
        });
        expect(result).toContain('Latitude');
    });

    it('rejects NaN longitude', () => {
        const result = validateLandmarkFormPayload({
            name: 'Test',
            latitude: 0,
            longitude: NaN,
        });
        expect(result).toContain('Longitude');
    });

    it('accepts boundary values', () => {
        expect(validateLandmarkFormPayload({ name: 'N', latitude: 90, longitude: 180 })).toBeNull();
        expect(validateLandmarkFormPayload({ name: 'S', latitude: -90, longitude: -180 })).toBeNull();
    });
});

describe('landmark generated operations and modal lifecycle', () => {
    let server: Awaited<ReturnType<typeof startApiServer>>;
    beforeAll(async () => { server = await startApiServer(); });
    afterAll(async () => { await server.close(); });
    beforeEach(() => {
        server.reset();
        setBrowserUrl(server.origin);
        document.body.innerHTML = `<input name="csrfmiddlewaretoken" value="${VALID_CSRF_TOKEN}">`;
    });
    afterEach(() => { document.body.replaceChildren(); });

    async function click(id: string) {
        const button = document.getElementById(id)!;
        await vi.waitFor(() => { expect(button.onclick).toBeTypeOf('function'); });
        await (button.onclick as unknown as () => Promise<void>)();
    }
    async function submitCreate() {
        const form = document.getElementById('landmark-create-form')!;
        await vi.waitFor(() => { expect(form.onsubmit).toBeTypeOf('function'); });
        document.querySelector<HTMLInputElement>('#landmark-create-form-name')!.value = '  New landmark  ';
        document.querySelector<HTMLInputElement>('#landmark-create-form-latitude')!.value = '12';
        document.querySelector<HTMLInputElement>('#landmark-create-form-longitude')!.value = '34';
        await (form.onsubmit as unknown as (event: Event) => Promise<void>)(new Event('submit', { cancelable: true }));
    }
    it('retains named function identity in its facade', () => {
        expect(LandmarkForms.openLandmarkCreateModal).toBe(openLandmarkCreateModal);
        expect(LandmarkForms.openLandmarkEditModal).toBe(openLandmarkEditModal);
        expect(LandmarkForms.openLandmarkDeleteModal).toBe(openLandmarkDeleteModal);
    });
    it('posts typed bulk transfer fields with the current CSRF token', async () => {
        server.reply({ json: { transferred: 2 } });
        openLandmarkBulkTransferModal({
            landmarks: [{ id: 'lm-1', name: 'Alpha' }, { id: 'lm-2', name: 'Beta' }],
            sourceCollection: { id: 'source', name: 'Source' },
            collections: [{ id: 'target', name: 'Target', can_write: true }],
        });
        await click('bulk-transfer-confirm');
        expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/landmark-collections/source/landmarks/transfer/' });
        expect(server.requests[0]!.headers['x-csrftoken']).toBe(VALID_CSRF_TOKEN);
        expect(JSON.parse(server.requests[0]!.body)).toEqual({ landmark_ids: ['lm-1', 'lm-2'], target_collection: 'target' });
    });
    it('posts bulk delete with its generated request body', async () => {
        server.reply({ json: { deleted: 2 } });
        openLandmarkBulkDeleteModal({
            landmarks: [{ id: 'lm-1', name: 'Alpha' }, { id: 'lm-2', name: 'Beta' }],
            sourceCollection: { id: 'source', name: 'Source' },
        });
        await click('bulk-delete-confirm');
        expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/landmark-collections/source/landmarks/bulk_delete/' });
        expect(JSON.parse(server.requests[0]!.body)).toEqual({ landmark_ids: ['lm-1', 'lm-2'] });
    });
    it('unwraps the documented creation envelope and sends trimmed fields', async () => {
        const landmark = { id: 'new', name: 'New landmark' };
        server.reply({ status: 201, json: { landmark } });
        const successes: unknown[] = [];
        openLandmarkCreateModal({ onSuccess: result => { successes.push(result); } });
        await submitCreate();
        expect(successes).toEqual([landmark]);
        expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/landmarks/' });
        expect(JSON.parse(server.requests[0]!.body)).toEqual({ name: 'New landmark', description: '', icon: 'DEFAULT', collection: null, latitude: 12, longitude: 34 });
        expect(document.getElementById('create-landmark-modal')).toBeNull();
    });
    it.each(['create', 'edit'] as const)('submits the selected icon from the %s modal handler', async mode => {
        server.reply({ json: { landmark: { id: 'one', name: 'Existing', icon: 'NOGO' } } });
        if (mode === 'create') {
            openLandmarkCreateModal({ lockedCollectionId: 'collection' });
        } else {
            openLandmarkEditModal({
                landmark: { id: 'one', name: 'Existing', icon: 'CAVE', collection: 'collection', latitude: 12, longitude: 34 },
                lockedCollectionId: 'collection',
            });
        }
        const form = document.getElementById(`landmark-${mode}-form`)!;
        await vi.waitFor(() => { expect(form.onsubmit).toBeTypeOf('function'); });
        expect((form.querySelector('input[name="icon"]:checked') as HTMLInputElement).value)
            .toBe(mode === 'create' ? 'DEFAULT' : 'CAVE');
        (form.querySelector('input[value="NOGO"]') as HTMLInputElement).click();
        if (mode === 'create') await submitCreate();
        else await (form.onsubmit as unknown as (event: Event) => Promise<void>)(new Event('submit', { cancelable: true }));
        expect(server.requests).toHaveLength(1);
        expect(server.requests[0]).toMatchObject({
            path: mode === 'create' ? '/api/v2/landmarks/' : '/api/v2/landmarks/one/',
            method: mode === 'create' ? 'POST' : 'PATCH',
        });
        expect(JSON.parse(server.requests[0]!.body)).toMatchObject({ icon: 'NOGO', collection: 'collection' });
    });
    it('renders serializer errors as text and omits the DELETE body/content-type', async () => {
        server.reply({ status: 400, json: { errors: { name: ['<img src=x>'] } } });
        openLandmarkCreateModal();
        await submitCreate();
        expect(document.getElementById('landmark-create-error')!.textContent).toBe('<img src=x>');
        expect(document.querySelector('#landmark-create-error img')).toBeNull();
        server.reply({ json: { message: 'Landmark deleted successfully.' } });
        const successes: unknown[] = [];
        openLandmarkDeleteModal({ landmark: { id: 'one', name: 'One' }, onSuccess: result => { successes.push(result); } });
        await click('confirm-delete-landmark');
        expect(server.requests[1]).toMatchObject({ method: 'DELETE', body: '' });
        expect(server.requests[1]!.headers).not.toHaveProperty('content-type');
        expect(successes).toEqual(['one']);
    });
    it('keeps an unexpected non-JSON response in the error path', async () => {
        server.reply({ text: 'unexpected html', headers: { 'Content-Type': 'text/html' } });
        const successes: unknown[] = [];
        openLandmarkCreateModal({ onSuccess: result => { successes.push(result); } });
        await submitCreate();
        expect(successes).toEqual([]);
        expect(document.getElementById('landmark-create-error')!.textContent).toBe('unexpected html');
    });
});

describe('landmark icon picker', () => {
    it('retains the icon while recoloring collection previews and submitting changes', () => {
        document.body.innerHTML = renderLandmarkFormHtml({
            mode: 'edit', formId: 'icons', errorElId: 'error',
            landmark: { id: 'one', name: 'Cave', icon: 'CAVE', collection: 'red', latitude: 1, longitude: 2 },
            collections: [{ id: 'red', color: '#ff0000', can_write: true }, { id: 'blue', color: '#0000ff', can_write: true }],
        });
        const form = document.getElementById('icons')!;
        landmarkPresentation.initializeLandmarkIconPicker(form, [{ id: 'red', color: '#ff0000' }, { id: 'blue', color: '#0000ff' }]);
        expect(form.querySelectorAll('input[name="icon"]')).toHaveLength(5);
        expect(readLandmarkFormPayload('icons').icon).toBe('CAVE');
        const collection = document.getElementById('icons-collection') as HTMLSelectElement;
        collection.value = 'blue';
        collection.dispatchEvent(new Event('change'));
        expect(form.querySelector<HTMLElement>('.landmark-icon-picker__choices')!.style.color).toBe('rgb(0, 0, 255)');
        expect(readLandmarkFormPayload('icons').icon).toBe('CAVE');
        (form.querySelector('input[value="NOGO"]') as HTMLInputElement).click();
        expect(readLandmarkFormPayload('icons').icon).toBe('NOGO');
    });
});

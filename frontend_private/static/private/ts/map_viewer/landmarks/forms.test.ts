import type { Mock } from 'vitest';
interface FixtureRequest { method: string; credentials: string; headers: Record<string, string>; body?: string }
interface FixtureResponse { ok: boolean; status: number; statusText?: string; text?: () => Promise<string> }
let fetch: Mock<(url: string, config: FixtureRequest) => Promise<FixtureResponse>>;
const installFetch = (mock: typeof fetch) => { fetch = mock; vi.stubGlobal('fetch', mock); };
type HtmlPrimitive = string | number | boolean | null | undefined;
vi.mock('../utils.ts', () => {
    const escapeHtml = (text: HtmlPrimitive) => {
        if (text === null || text === undefined) return '';
        const str = String(text);
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };
    const RAW = Symbol('RAW_HTML');
    type RawHTML = { [RAW]: true; value: string };
    type HtmlValue = HtmlPrimitive | RawHTML;
    return {
        Utils: {
            showNotification: vi.fn(),
            getCSRFToken: vi.fn(() => 'test-csrf'),
            escapeHtml,
            safeCssColor: (color: string, fallback = '#94a3b8') => (
                /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(String(color || ''))
                    ? color
                    : fallback
            ),
            raw: (html: string): RawHTML => ({ [RAW]: true, value: String(html) }),
            safeHtml: (strings: TemplateStringsArray, ...values: HtmlValue[]) => strings.reduce((r, s, i) => {
                if (i < values.length) {
                    const v = values[i];
                    if (v && typeof v === 'object' && v[RAW]) return r + s + v.value;
                    return r + s + escapeHtml(v as HtmlPrimitive);
                }
                return r + s;
            }, ''),
        },
    };
});

vi.mock('../components/modal.ts', () => ({
    Modal: {
        base: vi.fn((id: string, title: string, content: string, footer?: string | null) => `<div id="${id}">${content}${footer || ''}</div>`),
        open: vi.fn((id: string, html: string, cb?: (() => void) | null) => {
            document.body.insertAdjacentHTML('beforeend', html);
            if (cb) cb();
        }),
        close: vi.fn(),
    },
}));

import {
    LandmarkForms, openLandmarkCreateModal, openLandmarkEditModal, openLandmarkDeleteModal,
    openLandmarkBulkDeleteModal,
    openLandmarkBulkTransferModal,
    renderLandmarkFormHtml,
    readLandmarkFormPayload,
    validateLandmarkFormPayload,
} from './forms.ts';
import { Utils } from '../utils.ts';
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

describe('bulk landmark modals', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.clearAllMocks();
        vi.mocked(Utils).getCSRFToken.mockReturnValue(VALID_CSRF_TOKEN);
        vi.stubGlobal('Urls', {
            'private:landmark_collection_new': () => '/landmark-collections/new/',
            'api:v2:landmark-collection-landmarks-transfer': (sourceId: string) => `/api/collections/${sourceId}/landmarks/transfer/`,
            'api:v2:landmark-collection-landmarks-bulk-delete': (sourceId: string) => `/api/collections/${sourceId}/landmarks/bulk_delete/`,
        });
        installFetch(vi.fn(() => Promise.resolve({
            ok: true,
            status: 200,
            statusText: 'OK',
            text: () => Promise.resolve(JSON.stringify({ ok: true })),
        })));
    });

    it('posts bulk transfer with a valid-length CSRF header', async () => {
        openLandmarkBulkTransferModal({
            landmarks: [
                { id: 'lm-1', name: 'Alpha' },
                { id: 'lm-2', name: 'Beta' },
            ],
            sourceCollection: { id: 'source', name: 'Source Collection' },
            collections: [
                { id: 'source', name: 'Source Collection', can_write: true },
                { id: 'target', name: 'Target Collection', can_write: true },
            ],
        });

        await (document.getElementById('bulk-transfer-confirm')!.onclick as unknown as () => Promise<void>)();

        expect(fetch).toHaveBeenCalledTimes(1);
        const [url, config] = fetch.mock.calls[0]!;
        expect(url).toBe('/api/collections/source/landmarks/transfer/');
        expect(config.method).toBe('POST');
        expect(config.credentials).toBe('same-origin');
        expect(config.headers['X-CSRFToken']).toBe(VALID_CSRF_TOKEN);
        expect(config.headers['X-CSRFToken']!).toHaveLength(64);
        expect(JSON.parse(config.body!)).toEqual({
            landmark_ids: ['lm-1', 'lm-2'],
            target_collection: 'target',
        });
    });

    it('posts bulk delete with a valid-length CSRF header', async () => {
        openLandmarkBulkDeleteModal({
            landmarks: [
                { id: 'lm-1', name: 'Alpha' },
                { id: 'lm-2', name: 'Beta' },
            ],
            sourceCollection: { id: 'source', name: 'Source Collection' },
        });

        await (document.getElementById('bulk-delete-confirm')!.onclick as unknown as () => Promise<void>)();

        expect(fetch).toHaveBeenCalledTimes(1);
        const [url, config] = fetch.mock.calls[0]!;
        expect(url).toBe('/api/collections/source/landmarks/bulk_delete/');
        expect(config.method).toBe('POST');
        expect(config.credentials).toBe('same-origin');
        expect(config.headers['X-CSRFToken']).toBe(VALID_CSRF_TOKEN);
        expect(config.headers['X-CSRFToken']!).toHaveLength(64);
        expect(JSON.parse(config.body!)).toEqual({
            landmark_ids: ['lm-1', 'lm-2'],
        });
    });
});

describe('landmark modal transport and facade contracts', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.clearAllMocks();
        vi.stubGlobal('Urls', {
            'api:v2:landmarks': () => '/landmarks/',
            'api:v2:landmark-detail': (id: string) => `/landmarks/${id}/`,
        });
    });
    afterEach(() => { document.body.innerHTML = ''; vi.unstubAllGlobals(); });

    function submitCreate() {
        (document.getElementById('landmark-create-form-name') as HTMLInputElement).value = '  New landmark  ';
        (document.getElementById('landmark-create-form-latitude') as HTMLInputElement).value = '12';
        (document.getElementById('landmark-create-form-longitude') as HTMLInputElement).value = '34';
        return (document.getElementById('landmark-create-form')!.onsubmit as unknown as (event: Event) => Promise<void>)(new Event('submit', { cancelable: true }));
    }

    it('retains named function identity in its mutable facade', () => {
        expect(LandmarkForms.openLandmarkCreateModal).toBe(openLandmarkCreateModal);
        expect(LandmarkForms.openLandmarkEditModal).toBe(openLandmarkEditModal);
        expect(LandmarkForms.openLandmarkDeleteModal).toBe(openLandmarkDeleteModal);
        expect(LandmarkForms.renderLandmarkFormHtml).toBe(renderLandmarkFormHtml);
        expect(Object.isFrozen(LandmarkForms)).toBe(false);
    });

    it('returns null for 204 and posts trimmed fields before awaiting the success callback', async () => {
        const text = vi.fn();
        installFetch(vi.fn(() => Promise.resolve({ ok: true, status: 204, text })));
        const onSuccess = vi.fn(() => Promise.resolve());
        expect(openLandmarkCreateModal({ onSuccess })).toBeUndefined();
        await submitCreate();
        expect(text).not.toHaveBeenCalled();
        expect(onSuccess).toHaveBeenCalledWith(null);
        const [url, config] = fetch.mock.calls[0]!;
        expect(url).toBe('/landmarks/');
        expect(config.method).toBe('POST');
        expect(config.headers['Content-Type']).toBe('application/json');
        expect(JSON.parse(config.body!)).toEqual({ name: 'New landmark', description: '', collection: null, latitude: 12, longitude: 34 });
    });

    it('keeps non-JSON success data and catches callback rejection in the existing inline error path', async () => {
        installFetch(vi.fn(() => Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('accepted') })));
        const onSuccess = vi.fn(() => Promise.reject(new Error('Callback failed')));
        openLandmarkCreateModal({ onSuccess });
        await expect(submitCreate()).resolves.toBeUndefined();
        expect(onSuccess).toHaveBeenCalledWith('accepted');
        expect(document.getElementById('landmark-create-error')!.textContent).toBe('Callback failed');
    });

    it('renders serializer validation text without throwing and keeps DELETE body/content-type omitted', async () => {
        installFetch(vi.fn(() => Promise.resolve({ ok: false, status: 400, statusText: 'Bad Request', text: () => Promise.resolve('{"errors":{"name":["Name rejected"]}}') })));
        openLandmarkCreateModal();
        await expect(submitCreate()).resolves.toBeUndefined();
        expect(document.getElementById('landmark-create-error')!.textContent).toBe('Name rejected');
        const onSuccess = vi.fn();
        fetch.mockResolvedValue({ ok: true, status: 204 });
        openLandmarkDeleteModal({ landmark: { id: 'one', name: 'One' }, onSuccess });
        await (document.getElementById('confirm-delete-landmark')!.onclick as unknown as () => Promise<void>)();
        const [, config] = fetch.mock.calls[1]!;
        expect(config.method).toBe('DELETE');
        expect(config.body).toBeUndefined();
        expect(config.headers).not.toHaveProperty('Content-Type');
        expect(onSuccess).toHaveBeenCalledWith('one');
    });
});

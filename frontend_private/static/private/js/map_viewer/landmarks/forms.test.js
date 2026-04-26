vi.mock('../utils.js', () => {
    const escapeHtml = (text) => {
        if (text === null || text === undefined) return '';
        const str = String(text);
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };
    const RAW = Symbol('RAW_HTML');
    return {
        Utils: {
            showNotification: vi.fn(),
            getCSRFToken: vi.fn(() => 'test-csrf'),
            escapeHtml,
            safeCssColor: (color, fallback = '#94a3b8') => (
                /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(String(color || ''))
                    ? color
                    : fallback
            ),
            raw: (html) => ({ [RAW]: true, value: String(html) }),
            safeHtml: (strings, ...values) => strings.reduce((r, s, i) => {
                if (i < values.length) {
                    const v = values[i];
                    if (v && typeof v === 'object' && v[RAW]) return r + s + v.value;
                    return r + s + escapeHtml(v);
                }
                return r + s;
            }, ''),
        },
    };
});

vi.mock('../components/modal.js', () => ({
    Modal: {
        base: vi.fn((id, title, content, footer) => `<div id="${id}">${content}${footer || ''}</div>`),
        open: vi.fn((id, html, cb) => {
            document.body.insertAdjacentHTML('beforeend', html);
            if (cb) cb();
        }),
        close: vi.fn(),
    },
}));

import {
    renderLandmarkFormHtml,
    readLandmarkFormPayload,
    validateLandmarkFormPayload,
} from './forms.js';

describe('renderLandmarkFormHtml', () => {
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

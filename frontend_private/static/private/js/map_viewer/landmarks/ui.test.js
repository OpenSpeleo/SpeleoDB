import { LandmarkUI } from './ui.js';

vi.mock('./manager.js', () => ({
    LandmarkManager: {
        createLandmark: vi.fn(),
    },
}));

vi.mock('../state.js', () => ({
    State: {
        allLandmarks: new Map(),
    },
}));

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
            escapeHtml,
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
        base: vi.fn((id, title, content, footer) => `<div id="${id}">${content}${footer}</div>`),
        open: vi.fn((id, html, cb) => {
            document.body.insertAdjacentHTML('beforeend', html);
            if (cb) cb();
        }),
        close: vi.fn(),
    },
}));

describe('LandmarkUI coordinate formatting', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('openCreateModal renders formatted coordinates from numeric inputs', () => {
        LandmarkUI.openCreateModal([6.123456789, 46.987654321]);

        const html = document.body.innerHTML;
        expect(html).toContain('46.9876543');
        expect(html).toContain('6.1234568');
    });

    it('openCreateModal handles string coordinates without throwing', () => {
        expect(() => {
            LandmarkUI.openCreateModal(['6.123456789', '46.987654321']);
        }).not.toThrow();

        const html = document.body.innerHTML;
        expect(html).toContain('46.9876543');
        expect(html).toContain('6.1234568');
    });

    it('openCreateModal handles integer coordinates', () => {
        LandmarkUI.openCreateModal([6, 46]);

        const html = document.body.innerHTML;
        expect(html).toContain('46.0000000');
        expect(html).toContain('6.0000000');
    });

    it('openCreateModal cancel button uses data-close-modal for create-landmark-modal', () => {
        LandmarkUI.openCreateModal([6, 46]);

        const html = document.body.innerHTML;
        expect(html).toContain('data-close-modal="create-landmark-modal"');
        expect(html).not.toContain('landmark-details-modal');
    });
});

import { LandmarkUI } from './ui.js';

vi.mock('./manager.js', () => ({
    LandmarkManager: {
        createLandmark: vi.fn(),
    },
}));

vi.mock('../state.js', () => ({
    State: {
        allLandmarks: new Map(),
        landmarkCollections: new Map(),
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
        base: vi.fn((id, title, content, footer) => `<div id="${id}">${content}${footer}</div>`),
        open: vi.fn((id, html, cb) => {
            document.body.insertAdjacentHTML('beforeend', html);
            if (cb) cb();
        }),
        close: vi.fn(),
    },
}));

import { State } from '../state.js';

describe('LandmarkUI coordinate formatting', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        State.allLandmarks.clear();
        State.landmarkCollections.clear();
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

    it('defaults collection selectors to the personal collection when loaded', () => {
        State.landmarkCollections.set('shared-1', {
            id: 'shared-1',
            name: 'Shared',
            can_write: true,
            is_personal: false,
        });
        State.landmarkCollections.set('personal-1', {
            id: 'personal-1',
            name: 'Personal Landmarks',
            can_write: true,
            is_personal: true,
        });

        LandmarkUI.openCreateModal([6, 46]);

        const select = document.getElementById('landmark-collection');
        expect(select.value).toBe('personal-1');
        expect(select.textContent).toContain('Personal Landmarks (Private)');
    });

    it('labels personal landmark collections as private', () => {
        const label = LandmarkUI.getLandmarkCollectionLabel({
            collection_name: 'Personal Landmarks',
            is_personal_collection: true,
        });

        expect(label).toBe('Personal Landmarks (Private)');
    });

    it('groups landmarks by collection with personal group first', () => {
        State.landmarkCollections.set('shared-1', {
            id: 'shared-1',
            name: 'Shared',
            color: '#111111',
            can_write: false,
            is_personal: false,
        });
        State.landmarkCollections.set('personal-1', {
            id: 'personal-1',
            name: 'Personal Landmarks',
            color: '#222222',
            can_write: true,
            is_personal: true,
        });

        const groups = LandmarkUI.getLandmarkCollectionGroups([
            {
                id: 'lm-shared',
                name: 'Shared Point',
                collection: 'shared-1',
                collection_name: 'Shared',
                can_write: false,
            },
            {
                id: 'lm-personal',
                name: 'Personal Point',
                collection: 'personal-1',
                collection_name: 'Personal Landmarks',
                is_personal_collection: true,
                can_write: true,
            },
        ]);

        expect(groups).toHaveLength(2);
        expect(groups[0].id).toBe('personal-1');
        expect(groups[0].label).toBe('Personal Landmarks (Private)');
        expect(groups[0].color).toBe('#222222');
        expect(groups[1].canWrite).toBe(false);
    });

    it('renders landmark manager collection groups collapsed by default', () => {
        document.body.innerHTML = '<div id="landmark-manager-content"></div><div id="landmark-manager-modal"></div>';
        State.landmarkCollections.set('shared-1', {
            id: 'shared-1',
            name: 'Shared',
            color: '#111111',
            can_write: false,
            is_personal: false,
        });
        State.landmarkCollections.set('personal-1', {
            id: 'personal-1',
            name: 'Personal Landmarks',
            color: '#222222',
            can_write: true,
            is_personal: true,
        });
        State.allLandmarks.set('lm-shared', {
            id: 'lm-shared',
            name: 'Shared Point',
            latitude: 45,
            longitude: -122,
            collection: 'shared-1',
            collection_name: 'Shared',
            collection_color: '#111111',
            can_write: false,
            can_delete: false,
        });
        State.allLandmarks.set('lm-personal', {
            id: 'lm-personal',
            name: '<script>alert(1)</script>',
            latitude: 46,
            longitude: -123,
            collection: 'personal-1',
            collection_name: 'Personal Landmarks',
            collection_color: 'javascript:alert(1)',
            is_personal_collection: true,
            can_write: true,
            can_delete: true,
        });

        LandmarkUI.loadLandmarkManagerContent();

        const groups = document.querySelectorAll('.landmark-collection-group');
        expect(groups).toHaveLength(2);
        expect(groups[0].hasAttribute('open')).toBe(false);
        expect(groups[1].hasAttribute('open')).toBe(false);
        expect(groups[0].querySelector('.landmark-collection-toggle-icon')).not.toBeNull();
        expect(groups[0].querySelector('summary').title).toBe('Expand or collapse collection group');
        expect(document.body.innerHTML).toContain('.landmark-collection-group[open] .landmark-collection-toggle-icon');
        expect(document.body.textContent).toContain('Personal Landmarks (Private)');
        expect(document.body.textContent).toContain('Shared');
        expect(document.body.innerHTML).toContain('background-color: #222222');
        expect(document.body.innerHTML).toContain('fill="#94a3b8"');
        expect(document.body.innerHTML).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
        expect(document.body.innerHTML).not.toContain('<script>alert(1)</script>');
    });

    it('omits edit and delete controls for read-only landmarks', () => {
        State.allLandmarks.set('lm-readonly', {
            id: 'lm-readonly',
            name: 'Read Only',
            description: '',
            latitude: 45,
            longitude: -122,
            collection_name: 'Shared',
            creation_date: '2026-01-01T00:00:00Z',
            can_write: false,
            can_delete: false,
        });

        LandmarkUI.openDetailsModal('lm-readonly');

        expect(document.getElementById('edit-landmark-btn')).toBeNull();
        expect(document.getElementById('delete-landmark-btn')).toBeNull();
        expect(document.body.innerHTML).not.toContain('disabled');
    });
});

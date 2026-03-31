import { ExplorationLeadUI } from './ui.js';

vi.mock('./manager.js', () => ({
    ExplorationLeadManager: {
        createLead: vi.fn(),
        updateLead: vi.fn(),
        deleteLead: vi.fn(),
    },
}));

vi.mock('../state.js', () => ({
    State: {
        explorationLeads: new Map(),
    },
}));

vi.mock('../config.js', () => ({
    Config: {
        getScopedAccess: vi.fn(() => ({ write: false, delete: false })),
    },
}));

vi.mock('../map/layers.js', () => ({
    Layers: {
        refreshExplorationLeadsLayer: vi.fn(),
        reorderLayers: vi.fn(),
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

import { State } from '../state.js';

describe('ExplorationLeadUI coordinate formatting', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        window.MAPVIEWER_CONTEXT = { icons: { explorationLead: 'https://example.test/lead.png' } };
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        delete window.MAPVIEWER_CONTEXT;
    });

    describe('showCreateModal', () => {
        it('renders formatted coordinates from numeric inputs', () => {
            ExplorationLeadUI.showCreateModal([6.123456789, 46.987654321], 'Line A', 'p1');

            const html = document.body.innerHTML;
            expect(html).toContain('46.9876543');
            expect(html).toContain('6.1234568');
        });

        it('handles string coordinates without throwing', () => {
            expect(() => {
                ExplorationLeadUI.showCreateModal(['6.123456789', '46.987654321'], 'Line A', 'p1');
            }).not.toThrow();

            const html = document.body.innerHTML;
            expect(html).toContain('46.9876543');
            expect(html).toContain('6.1234568');
        });
    });

    describe('showDetailsModal', () => {
        it('renders formatted coordinates from numeric state values', () => {
            State.explorationLeads.set('lead-1', {
                id: 'lead-1',
                coordinates: [6.123456789, 46.987654321],
                description: 'Test lead',
                projectId: 'p1',
                lineName: 'Line A',
            });

            ExplorationLeadUI.showDetailsModal('lead-1');

            const html = document.body.innerHTML;
            expect(html).toContain('46.9876543');
            expect(html).toContain('6.1234568');
        });

        it('handles string coordinates in state without throwing', () => {
            State.explorationLeads.set('lead-2', {
                id: 'lead-2',
                coordinates: ['6.5', '46.5'],
                description: 'Test lead',
                projectId: 'p1',
                lineName: 'Line B',
            });

            expect(() => {
                ExplorationLeadUI.showDetailsModal('lead-2');
            }).not.toThrow();

            const html = document.body.innerHTML;
            expect(html).toContain('46.5000000');
            expect(html).toContain('6.5000000');
        });
    });
});

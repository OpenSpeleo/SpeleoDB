import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { StationExperiments } from './experiments.js';
import { API } from '../api.js';
import { Config } from '../config.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';

vi.mock('../api.js', () => ({
    API: {
        getExperiments: vi.fn(),
        getExperimentData: vi.fn(),
    },
}));

vi.mock('../config.js', () => ({
    Config: {
        getStationAccess: vi.fn(() => ({ write: true, delete: true })),
        getScopedAccess: vi.fn(() => ({ write: true, delete: true })),
    },
    DEFAULTS: { UI: {} },
}));

vi.mock('../state.js', () => ({
    State: {
        allStations: new Map(),
        allSurfaceStations: new Map(),
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
            showLoadingOverlay: vi.fn(() => document.createElement('div')),
            hideLoadingOverlay: vi.fn(),
            escapeHtml: vi.fn(escapeHtml),
            safeCssColor: vi.fn((c, fb) => /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(c) ? c : (fb || '#94a3b8')),
            sanitizeUrl: vi.fn((url) => url || ''),
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

const xssName = '<script>alert(1)</script>';
const xssDescription = '<img src=x onerror=alert(1)>';
const fieldUuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

function baseExperiment(overrides = {}) {
    return {
        id: 'exp-1',
        name: xssName,
        code: 'CODE',
        description: xssDescription,
        is_active: true,
        experiment_fields: {
            [fieldUuid]: {
                id: fieldUuid,
                name: 'Notes',
                type: 'text',
                order: 0,
                required: false,
            },
        },
        ...overrides,
    };
}

describe('StationExperiments XSS', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        document.body.appendChild(container);
        State.allStations = new Map();
        State.allSurfaceStations = new Map();
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        delete window.updateExperimentTable;
        delete window.deleteExperimentTableRow;
    });

    it('escapes experiment name in select option text', async () => {
        const stationId = 'st-1';
        State.allStations.set(stationId, { id: stationId, project: 'proj-1' });
        API.getExperiments.mockResolvedValue({ data: [baseExperiment()] });
        API.getExperimentData.mockResolvedValue({ data: [] });

        await StationExperiments.render(stationId, container);

        const html = container.innerHTML;
        expect(html).not.toMatch(/<script>alert\(1\)<\/script>/i);
        expect(html).toContain('&lt;script&gt;');
        expect(Utils.escapeHtml).toHaveBeenCalledWith(xssName);
    });

    it('escapes experiment description when an experiment is selected', async () => {
        const stationId = 'st-1';
        State.allStations.set(stationId, { id: stationId, project: 'proj-1' });
        API.getExperiments.mockResolvedValue({ data: [baseExperiment()] });
        API.getExperimentData.mockResolvedValue({ data: [] });

        await StationExperiments.render(stationId, container);

        const sel = container.querySelector('#experiment-selector');
        sel.value = 'exp-1';
        sel.dispatchEvent(new Event('change', { bubbles: true }));

        await vi.waitFor(() => {
            expect(container.innerHTML).toContain('Data Records');
        });

        const html = container.innerHTML;
        expect(html).not.toMatch(/<img[^>]*onerror/i);
        expect(html).toContain('&lt;img');
        expect(Utils.escapeHtml).toHaveBeenCalledWith(xssDescription);
    });

    it('escapes text field values in table cells', async () => {
        const stationId = 'st-1';
        const cellPayload = '<svg onload=alert(1)>';
        State.allStations.set(stationId, { id: stationId, project: 'proj-1' });
        API.getExperiments.mockResolvedValue({ data: [baseExperiment()] });
        API.getExperimentData.mockResolvedValue({
            data: [{ id: 'row-1', data: { [fieldUuid]: cellPayload } }],
        });

        await StationExperiments.render(stationId, container);

        const sel = container.querySelector('#experiment-selector');
        sel.value = 'exp-1';
        sel.dispatchEvent(new Event('change', { bubbles: true }));

        await vi.waitFor(() => {
            expect(container.querySelector('tbody')).toBeTruthy();
        });

        const html = container.innerHTML;
        expect(html).not.toMatch(/<svg[^>]*onload/i);
        expect(html).toContain('&lt;svg');
    });

    it('escapes double quotes in data-station-id and related attributes on Add Record', async () => {
        const stationId = 'ab\" onclick=\"evil\" data-x=';
        const projectId = 'proj\"p';
        State.allStations.set(stationId, { id: stationId, project: projectId });
        API.getExperiments.mockResolvedValue({ data: [baseExperiment({ name: 'Safe', description: '' })] });
        API.getExperimentData.mockResolvedValue({ data: [] });

        await StationExperiments.render(stationId, container);

        const sel = container.querySelector('#experiment-selector');
        sel.value = 'exp-1';
        sel.dispatchEvent(new Event('change', { bubbles: true }));

        await vi.waitFor(() => {
            expect(container.querySelector('#add-experiment-row-btn')).toBeTruthy();
        });

        const btn = container.querySelector('#add-experiment-row-btn');
        expect(btn.getAttribute('data-station-id')).toBe(stationId);
        expect(btn.getAttribute('data-project-id')).toBe(projectId);
        const raw = container.innerHTML;
        expect(raw).not.toMatch(/data-station-id="[^"]*"\s+onclick/i);
        expect(raw).toContain('&quot;');
    });
});

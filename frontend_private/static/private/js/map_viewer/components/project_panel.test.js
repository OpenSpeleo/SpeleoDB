import { ProjectPanel } from './project_panel.js';
import { Config, DEFAULTS } from '../config.js';
import { Layers } from '../map/layers.js';
import { State } from '../state.js';
import { Colors } from '../map/colors.js';

vi.mock('../config.js', () => ({
    Config: {
        projects: [],
        getProjectById: vi.fn(),
    },
    DEFAULTS: Object.freeze({
        MAP: {
            FIT_BOUNDS_PADDING: 50,
            FIT_BOUNDS_MAX_ZOOM: 16,
        },
        STORAGE_KEYS: {
            COUNTRY_COLLAPSED: 'speleo_country_collapsed',
            COUNTRY_VISIBILITY: 'speleo_country_visibility',
        },
        UI: {
            COUNTRY_GROUP_TRANSITION_MS: 250,
        },
        COLORS: {
            FALLBACK: '#94a3b8',
        },
    }),
}));

vi.mock('../map/layers.js', () => ({
    Layers: {
        isProjectVisible: vi.fn(() => true),
        toggleProjectVisibility: vi.fn(),
        applyProjectVisibility: vi.fn(),
        recomputeActiveDepthDomain: vi.fn(),
        applyDepthLineColors: vi.fn(),
        colorMode: 'project',
    },
}));

vi.mock('../state.js', () => ({
    State: {
        projectBounds: new Map(),
        map: null,
    },
}));

vi.mock('../map/colors.js', () => ({
    Colors: {
        getProjectColor: vi.fn(() => '#e41a1c'),
    },
}));

describe('ProjectPanel', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="map-wrapper"><div id="map"></div></div>';
        Config.projects = [];
        State.projectBounds = new Map();
        State.map = null;
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    // ------------------------------------------------------------------ //
    // init
    // ------------------------------------------------------------------ //

    describe('init', () => {
        it('creates panel and binds events', () => {
            ProjectPanel.init();

            expect(document.getElementById('project-panel')).not.toBeNull();
            expect(document.getElementById('project-panel-minimized')).not.toBeNull();
            expect(document.getElementById('panel-toggle')).not.toBeNull();
            expect(document.getElementById('panel-expand')).not.toBeNull();
        });
    });

    // ------------------------------------------------------------------ //
    // render
    // ------------------------------------------------------------------ //

    describe('render', () => {
        it('creates project panel if it does not exist', () => {
            ProjectPanel.render();

            expect(document.getElementById('project-panel')).not.toBeNull();
            expect(document.getElementById('project-panel-minimized')).not.toBeNull();
            expect(document.getElementById('project-list')).not.toBeNull();
        });

        it('does not duplicate panel on repeated render calls', () => {
            ProjectPanel.render();
            ProjectPanel.render();

            expect(document.querySelectorAll('#project-panel').length).toBe(1);
        });
    });

    // ------------------------------------------------------------------ //
    // refreshList
    // ------------------------------------------------------------------ //

    describe('refreshList', () => {
        it('renders a button for each project', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha' },
                { id: 'p-2', name: 'Beta' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);

            ProjectPanel.render();

            expect(document.querySelectorAll('.project-button').length).toBe(2);
        });

        it('sorts projects alphabetically (case-insensitive)', () => {
            Config.projects = [
                { id: 'p-2', name: 'Zebra' },
                { id: 'p-1', name: 'alpha' },
            ];

            ProjectPanel.render();

            const items = document.querySelectorAll('.project-button');
            expect(items[0].textContent).toContain('alpha');
            expect(items[1].textContent).toContain('Zebra');
        });

        it('applies opacity class for hidden projects', () => {
            Config.projects = [{ id: 'p-1', name: 'Test' }];
            Layers.isProjectVisible.mockReturnValue(false);

            ProjectPanel.render();

            const item = document.querySelector('.project-button');
            expect(item.classList.contains('opacity-50')).toBe(true);
        });

        it('does not apply opacity class for visible projects', () => {
            Config.projects = [{ id: 'p-1', name: 'Test' }];
            Layers.isProjectVisible.mockReturnValue(true);

            ProjectPanel.render();

            const item = document.querySelector('.project-button');
            expect(item.classList.contains('opacity-50')).toBe(false);
        });

        it('checks the toggle for visible projects', () => {
            Config.projects = [{ id: 'p-1', name: 'Test' }];
            Layers.isProjectVisible.mockReturnValue(true);

            ProjectPanel.render();

            const checkbox = document.querySelector('.project-button input[type="checkbox"]');
            expect(checkbox.checked).toBe(true);
        });

        it('unchecks the toggle for hidden projects', () => {
            Config.projects = [{ id: 'p-1', name: 'Test' }];
            Layers.isProjectVisible.mockReturnValue(false);

            ProjectPanel.render();

            const checkbox = document.querySelector('.project-button input[type="checkbox"]');
            expect(checkbox.checked).toBe(false);
        });

        it('uses gray dot color for hidden projects', () => {
            Config.projects = [{ id: 'p-1', name: 'Test' }];
            Layers.isProjectVisible.mockReturnValue(false);

            ProjectPanel.render();

            const dot = document.querySelector('.project-color-dot');
            expect(dot.style.backgroundColor).toBe('rgb(148, 163, 184)'); // #94a3b8
        });

        it('renders empty list when no projects exist', () => {
            Config.projects = [];

            ProjectPanel.render();

            expect(document.querySelectorAll('.project-button').length).toBe(0);
        });
    });

    // ------------------------------------------------------------------ //
    // toggleProject
    // ------------------------------------------------------------------ //

    describe('toggleProject', () => {
        it('delegates to Layers.toggleProjectVisibility', () => {
            Config.projects = [{ id: 'p-1', name: 'Test' }];
            Config.getProjectById.mockReturnValue({ id: 'p-1', name: 'Test' });
            ProjectPanel.render();

            ProjectPanel.toggleProject('p-1', false);

            expect(Layers.toggleProjectVisibility).toHaveBeenCalledWith('p-1', false);
        });

        it('refreshes the list after toggling', () => {
            Config.projects = [{ id: 'p-1', name: 'Test' }];
            Config.getProjectById.mockReturnValue({ id: 'p-1', name: 'Test' });
            ProjectPanel.render();
            const spy = vi.spyOn(ProjectPanel, 'refreshList');

            ProjectPanel.toggleProject('p-1', true);

            expect(spy).toHaveBeenCalled();
            spy.mockRestore();
        });
    });

    // ------------------------------------------------------------------ //
    // bindEvents
    // ------------------------------------------------------------------ //

    describe('bindEvents', () => {
        it('minimizes panel when toggle button is clicked', () => {
            ProjectPanel.init();

            document.getElementById('panel-toggle').click();

            expect(document.getElementById('project-panel').style.display).toBe('none');
            expect(document.getElementById('project-panel-minimized').style.display).toBe('block');
        });

        it('expands panel when expand button is clicked', () => {
            ProjectPanel.init();

            document.getElementById('panel-toggle').click();
            document.getElementById('panel-expand').click();

            expect(document.getElementById('project-panel').style.display).toBe('block');
            expect(document.getElementById('project-panel-minimized').style.display).toBe('none');
        });
    });

    // ------------------------------------------------------------------ //
    // getProjectColor
    // ------------------------------------------------------------------ //

    describe('getProjectColor', () => {
        it('delegates to Colors.getProjectColor', () => {
            Colors.getProjectColor.mockReturnValue('#00ff00');

            const color = ProjectPanel.getProjectColor('p-1');

            expect(Colors.getProjectColor).toHaveBeenCalledWith('p-1');
            expect(color).toBe('#00ff00');
        });
    });

    // ------------------------------------------------------------------ //
    // Country grouping
    // ------------------------------------------------------------------ //

    describe('country grouping', () => {
        it('renders country groups when projects have country field', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
                { id: 'p-2', name: 'Beta', country: 'ES' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();

            expect(document.querySelectorAll('.country-group').length).toBe(2);
        });

        it('sorts groups alphabetically by country name', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
                { id: 'p-2', name: 'Beta', country: 'ES' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();

            const groups = document.querySelectorAll('.country-group');
            expect(groups[0].dataset.country).toBe('ES');
            expect(groups[1].dataset.country).toBe('FR');
        });

        it('renders flat list when no projects have country field', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha' },
                { id: 'p-2', name: 'Beta' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();

            expect(document.querySelectorAll('.country-group').length).toBe(0);
            expect(document.querySelectorAll('.project-button').length).toBe(2);
        });

        it('each group has a country-group-header element', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
                { id: 'p-2', name: 'Beta', country: 'ES' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();

            expect(document.querySelectorAll('.country-group-header').length).toBe(2);
        });
    });

    // ------------------------------------------------------------------ //
    // Country visibility toggle (two-level gate)
    // ------------------------------------------------------------------ //

    describe('country visibility toggle', () => {
        beforeEach(() => {
            vi.stubGlobal('localStorage', {
                _store: {},
                getItem: vi.fn(function(key) { return this._store[key] || null; }),
                setItem: vi.fn(function(key, val) { this._store[key] = val; }),
            });
        });

        afterEach(() => {
            vi.unstubAllGlobals();
        });

        it('applies country-off visibility on initial load (init)', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
                { id: 'p-2', name: 'Beta', country: 'FR' },
                { id: 'p-3', name: 'Gamma', country: 'ES' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            // Simulate localStorage having FR set to hidden from a previous session
            localStorage._store['speleo_country_visibility'] = JSON.stringify({ FR: false });

            ProjectPanel.init();

            expect(Layers.applyProjectVisibility).toHaveBeenCalledWith('p-1', false);
            expect(Layers.applyProjectVisibility).toHaveBeenCalledWith('p-2', false);
            expect(Layers.applyProjectVisibility).not.toHaveBeenCalledWith('p-3', false);
        });

        it('does not call applyProjectVisibility on init when all countries are visible', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);

            ProjectPanel.init();

            expect(Layers.applyProjectVisibility).not.toHaveBeenCalled();
        });

        it('country toggle OFF hides projects on map via applyProjectVisibility', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
                { id: 'p-2', name: 'Beta', country: 'FR' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();

            const toggle = document.querySelector('.country-toggle');
            toggle.checked = false;
            toggle.dispatchEvent(new Event('change', { bubbles: true }));

            expect(Layers.applyProjectVisibility).toHaveBeenCalledWith('p-1', false);
            expect(Layers.applyProjectVisibility).toHaveBeenCalledWith('p-2', false);
        });

        it('country toggle OFF does not call toggleProjectVisibility (preserves prefs)', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();
            Layers.toggleProjectVisibility.mockClear();

            const toggle = document.querySelector('.country-toggle');
            toggle.checked = false;
            toggle.dispatchEvent(new Event('change', { bubbles: true }));

            expect(Layers.toggleProjectVisibility).not.toHaveBeenCalled();
        });

        it('country toggle ON restores only individually-ON projects', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
                { id: 'p-2', name: 'Beta', country: 'FR' },
            ];
            // p-1 is individually ON, p-2 is individually OFF
            Layers.isProjectVisible.mockImplementation((id) => id === 'p-1');
            // First turn country OFF
            localStorage._store = {};
            ProjectPanel.render();

            const toggle = document.querySelector('.country-toggle');
            toggle.checked = false;
            toggle.dispatchEvent(new Event('change', { bubbles: true }));
            Layers.applyProjectVisibility.mockClear();

            // Now turn country back ON
            const toggle2 = document.querySelector('.country-toggle');
            toggle2.checked = true;
            toggle2.dispatchEvent(new Event('change', { bubbles: true }));

            // p-1 was individually ON -> should be visible
            expect(Layers.applyProjectVisibility).toHaveBeenCalledWith('p-1', true);
            // p-2 was individually OFF -> should stay hidden
            expect(Layers.applyProjectVisibility).toHaveBeenCalledWith('p-2', false);
        });

        it('shows country toggle as checked by default (country visible)', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();

            const toggle = document.querySelector('.country-toggle');
            expect(toggle.checked).toBe(true);
        });

        it('persists country visibility to localStorage', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();

            const toggle = document.querySelector('.country-toggle');
            toggle.checked = false;
            toggle.dispatchEvent(new Event('change', { bubbles: true }));

            expect(localStorage.setItem).toHaveBeenCalledWith(
                'speleo_country_visibility',
                expect.any(String)
            );
        });

        it('country toggle triggers depth domain recomputation', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();
            Layers.recomputeActiveDepthDomain.mockClear();

            const toggle = document.querySelector('.country-toggle');
            toggle.checked = false;
            toggle.dispatchEvent(new Event('change', { bubbles: true }));

            expect(Layers.recomputeActiveDepthDomain).toHaveBeenCalled();
        });

        it('individual toggle ON when country OFF saves pref but stays hidden on map', () => {
            Config.projects = [{ id: 'p-1', name: 'Alpha', country: 'FR' }];
            Config.getProjectById.mockReturnValue({ id: 'p-1', name: 'Alpha', country: 'FR' });
            Layers.isProjectVisible.mockReturnValue(false);
            localStorage._store[DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY] = JSON.stringify({ FR: false });

            ProjectPanel.refreshList();
            ProjectPanel.toggleProject('p-1', true);

            expect(Layers.toggleProjectVisibility).toHaveBeenCalledWith('p-1', true);
            expect(Layers.applyProjectVisibility).toHaveBeenCalledWith('p-1', false);
        });
    });

    // ------------------------------------------------------------------ //
    // Country collapse/expand (UI accordion)
    // ------------------------------------------------------------------ //

    describe('country collapse/expand', () => {
        beforeEach(() => {
            vi.stubGlobal('localStorage', {
                _store: {},
                getItem: vi.fn(function(key) { return this._store[key] || null; }),
                setItem: vi.fn(function(key, val) { this._store[key] = val; }),
            });
        });

        afterEach(() => {
            vi.unstubAllGlobals();
        });

        it('clicking group header toggles collapsed class', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();

            const header = document.querySelector('.country-group-header');
            header.click();

            const group = document.querySelector('.country-group');
            expect(group.classList.contains('collapsed')).toBe(true);
        });

        it('persists collapse state to localStorage', () => {
            Config.projects = [
                { id: 'p-1', name: 'Alpha', country: 'FR' },
            ];
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();

            const header = document.querySelector('.country-group-header');
            header.click();

            expect(localStorage.setItem).toHaveBeenCalledWith(
                'speleo_country_collapsed',
                expect.any(String)
            );
        });
    });

    // ------------------------------------------------------------------ //
    // localStorage corruption
    // ------------------------------------------------------------------ //

    describe('localStorage corruption', () => {
        beforeEach(() => {
            vi.stubGlobal('localStorage', {
                _store: {},
                getItem: vi.fn(function(key) { return this._store[key] || null; }),
                setItem: vi.fn(function(key, val) { this._store[key] = val; }),
            });
        });

        afterEach(() => {
            vi.unstubAllGlobals();
        });

        it('handles JSON null in country visibility gracefully', () => {
            localStorage._store[DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY] = 'null';
            expect(() => ProjectPanel.isCountryVisible('FR')).not.toThrow();
            expect(ProjectPanel.isCountryVisible('FR')).toBe(true);
        });

        it('handles JSON number in country visibility gracefully', () => {
            localStorage._store[DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY] = '42';
            expect(() => ProjectPanel.isCountryVisible('FR')).not.toThrow();
        });

        it('handles JSON array in country visibility gracefully', () => {
            localStorage._store[DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY] = '[1,2]';
            expect(() => ProjectPanel.isCountryVisible('FR')).not.toThrow();
        });

        it('handles invalid JSON in country visibility gracefully', () => {
            localStorage._store[DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY] = '{broken';
            expect(() => ProjectPanel.isCountryVisible('FR')).not.toThrow();
            expect(ProjectPanel.isCountryVisible('FR')).toBe(true);
        });

        it('handles JSON null in collapsed countries gracefully', () => {
            localStorage._store[DEFAULTS.STORAGE_KEYS.COUNTRY_COLLAPSED] = 'null';
            Config.projects = [{ id: 'p-1', name: 'Alpha', country: 'FR' }];
            expect(() => ProjectPanel.refreshList()).not.toThrow();
        });
    });

    // ------------------------------------------------------------------ //
    // Stored color
    // ------------------------------------------------------------------ //

    describe('stored color', () => {
        it('uses stored project color for the color dot', () => {
            Config.projects = [{ id: 'p-1', name: 'Test' }];
            Colors.getProjectColor.mockReturnValue('#ff5500');
            Layers.isProjectVisible.mockReturnValue(true);
            ProjectPanel.render();

            const dot = document.querySelector('.project-color-dot');
            expect(dot.style.backgroundColor).toBe('rgb(255, 85, 0)');
        });
    });
});

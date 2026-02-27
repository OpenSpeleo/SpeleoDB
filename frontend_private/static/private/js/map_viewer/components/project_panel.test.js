import { ProjectPanel } from './project_panel.js';
import { Config } from '../config.js';
import { Layers } from '../map/layers.js';
import { State } from '../state.js';
import { Colors } from '../map/colors.js';

vi.mock('../config.js', () => ({
    Config: {
        projects: [],
    },
}));

vi.mock('../map/layers.js', () => ({
    Layers: {
        isProjectVisible: vi.fn(() => true),
        toggleProjectVisibility: vi.fn(),
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

            const checkbox = document.querySelector('input[type="checkbox"]');
            expect(checkbox.checked).toBe(true);
        });

        it('unchecks the toggle for hidden projects', () => {
            Config.projects = [{ id: 'p-1', name: 'Test' }];
            Layers.isProjectVisible.mockReturnValue(false);

            ProjectPanel.render();

            const checkbox = document.querySelector('input[type="checkbox"]');
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
            ProjectPanel.render();

            ProjectPanel.toggleProject('p-1', false);

            expect(Layers.toggleProjectVisibility).toHaveBeenCalledWith('p-1', false);
        });

        it('refreshes the list after toggling', () => {
            Config.projects = [{ id: 'p-1', name: 'Test' }];
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

            // Minimize first
            document.getElementById('panel-toggle').click();
            // Then expand
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
});

import { StationLogs } from './logs.js';
import { API } from '../api.js';
import { Utils } from '../utils.js';
import { Config } from '../config.js';
import { State } from '../state.js';

vi.mock('../api.js', () => ({
    API: {
        getStationLogs: vi.fn(),
        createStationLog: vi.fn(),
        updateStationLog: vi.fn(),
        deleteStationLog: vi.fn(),
    },
}));

vi.mock('../utils.js', () => ({
    Utils: {
        showNotification: vi.fn(),
        showLoadingOverlay: vi.fn(() => document.createElement('div')),
        hideLoadingOverlay: vi.fn(),
        formatJournalDate: vi.fn((d) => d || ''),
        filenameFromUrl: vi.fn((url) => url?.split('/').pop() || ''),
    },
}));

vi.mock('../config.js', () => ({
    Config: {
        getStationAccess: vi.fn(() => ({
            write: true,
            delete: true,
            scopeType: 'project',
            scopeId: 'proj-1',
            read: true,
        })),
    },
}));

vi.mock('../state.js', () => ({
    State: {
        allStations: new Map(),
        allSurfaceStations: new Map(),
    },
}));

vi.mock('../components/upload.js', () => ({
    createProgressBarHTML: vi.fn((id) => `<div id="${id}-container" class="hidden"></div>`),
    UploadProgressController: vi.fn().mockImplementation(() => ({
        show: vi.fn(),
        hide: vi.fn(),
        update: vi.fn(),
        upload: vi.fn().mockResolvedValue({}),
    })),
}));

describe('StationLogs', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'station-modal-content';
        document.body.appendChild(container);
        State.allStations = new Map();
        State.allSurfaceStations = new Map();
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    // ------------------------------------------------------------------ //
    // render
    // ------------------------------------------------------------------ //

    describe('render', () => {
        const stationId = 'st-1';

        beforeEach(() => {
            State.allStations.set(stationId, { id: stationId, project: 'proj-1' });
        });

        it('renders journal entries when logs exist (response.data format)', async () => {
            const logs = [
                { id: 'log-1', title: 'First Entry', notes: 'Some notes', creation_date: '2024-01-01', created_by: 'Alice' },
            ];
            API.getStationLogs.mockResolvedValue({ data: logs });

            await StationLogs.render(stationId, container);

            expect(container.innerHTML).toContain('First Entry');
            expect(container.innerHTML).toContain('Some notes');
            expect(Utils.showLoadingOverlay).toHaveBeenCalled();
            expect(Utils.hideLoadingOverlay).toHaveBeenCalled();
        });

        it('handles raw array response format', async () => {
            const logs = [{ id: 'log-1', title: 'Raw Array', notes: 'test' }];
            API.getStationLogs.mockResolvedValue(logs);

            await StationLogs.render(stationId, container);

            expect(container.innerHTML).toContain('Raw Array');
        });

        it('handles response.results format', async () => {
            const logs = [{ id: 'log-1', title: 'Results Format', notes: 'test' }];
            API.getStationLogs.mockResolvedValue({ results: logs });

            await StationLogs.render(stationId, container);

            expect(container.innerHTML).toContain('Results Format');
        });

        it('renders empty state when no logs exist', async () => {
            API.getStationLogs.mockResolvedValue({ data: [] });

            await StationLogs.render(stationId, container);

            expect(container.innerHTML).toContain('No Journal Entries Yet');
        });

        it('renders enabled new-entry button when user has write access', async () => {
            Config.getStationAccess.mockReturnValue({ write: true, delete: false });
            API.getStationLogs.mockResolvedValue({ data: [] });

            await StationLogs.render(stationId, container);

            const btn = document.getElementById('new-log-entry-btn');
            expect(btn).not.toBeNull();
        });

        it('does not render enabled new-entry button without write access', async () => {
            Config.getStationAccess.mockReturnValue({ write: false, delete: false });
            API.getStationLogs.mockResolvedValue({ data: [] });

            await StationLogs.render(stationId, container);

            expect(document.getElementById('new-log-entry-btn')).toBeNull();
            expect(container.innerHTML).toContain('cursor-not-allowed');
        });

        it('renders error state on API failure', async () => {
            API.getStationLogs.mockRejectedValue(new Error('Network error'));

            await StationLogs.render(stationId, container);

            expect(container.innerHTML).toContain('Failed to load journal entries');
            expect(Utils.hideLoadingOverlay).toHaveBeenCalled();
        });

        it('looks up surface stations when subsurface lookup misses', async () => {
            State.allStations = new Map();
            State.allSurfaceStations.set(stationId, {
                id: stationId, network: 'net-1', station_type: 'surface',
            });
            API.getStationLogs.mockResolvedValue({ data: [] });

            await StationLogs.render(stationId, container);

            expect(Config.getStationAccess).toHaveBeenCalledWith(
                expect.objectContaining({ network: 'net-1' })
            );
        });
    });

    // ------------------------------------------------------------------ //
    // renderEntry
    // ------------------------------------------------------------------ //

    describe('renderEntry', () => {
        it('renders entry with title and notes', () => {
            const log = { id: 'log-1', title: 'Test Entry', notes: 'Test notes', creation_date: '2024-01-01', created_by: 'Alice' };

            const html = StationLogs.renderEntry(log, true, true);

            expect(html).toContain('Test Entry');
            expect(html).toContain('Test notes');
            expect(html).toContain('data-log-id="log-1"');
        });

        it('uses "Untitled Entry" when title is missing', () => {
            const log = { id: 'log-1', notes: 'notes' };

            const html = StationLogs.renderEntry(log, false, false);

            expect(html).toContain('Untitled Entry');
        });

        it('renders attachment link when present', () => {
            const log = { id: 'log-1', title: 'T', notes: '', attachment: 'https://example.com/report.pdf' };

            const html = StationLogs.renderEntry(log, false, false);

            expect(html).toContain('ATTACHMENT');
            expect(html).toContain('https://example.com/report.pdf');
        });

        it('does not render attachment section when absent', () => {
            const log = { id: 'log-1', title: 'T', notes: '' };

            const html = StationLogs.renderEntry(log, false, false);

            expect(html).not.toContain('ATTACHMENT');
        });

        it('escapes HTML entities in notes to prevent XSS', () => {
            const log = { id: 'log-1', title: 'T', notes: '<script>alert("xss")</script>' };

            const html = StationLogs.renderEntry(log, false, false);

            expect(html).not.toContain('<script>');
            expect(html).toContain('&lt;script&gt;');
        });

        it('renders clickable edit button with write access', () => {
            const log = { id: 'log-1', title: 'T', notes: '' };

            const html = StationLogs.renderEntry(log, true, false);

            expect(html).toContain('edit-log-btn');
        });

        it('renders disabled edit button without write access', () => {
            const log = { id: 'log-1', title: 'T', notes: '' };

            const html = StationLogs.renderEntry(log, false, false);

            expect(html).toContain('cursor-not-allowed');
            expect(html).not.toContain('edit-log-btn');
        });

        it('renders clickable delete button for admins', () => {
            const log = { id: 'log-1', title: 'T', notes: '' };

            const html = StationLogs.renderEntry(log, false, true);

            expect(html).toContain('delete-log-btn');
        });

        it('renders disabled delete button for non-admins', () => {
            const log = { id: 'log-1', title: 'T', notes: '' };

            const html = StationLogs.renderEntry(log, false, false);

            expect(html).toContain('Only admins can delete');
        });
    });

    // ------------------------------------------------------------------ //
    // openCreateModal
    // ------------------------------------------------------------------ //

    describe('openCreateModal', () => {
        it('inserts create modal into DOM with form elements', () => {
            StationLogs.openCreateModal('st-1');

            expect(document.getElementById('log-entry-modal')).not.toBeNull();
            expect(document.getElementById('log-entry-form')).not.toBeNull();
            expect(document.getElementById('log-title')).not.toBeNull();
            expect(document.getElementById('log-notes')).not.toBeNull();
            expect(document.getElementById('log-attachment')).not.toBeNull();
        });

        it('closes modal when close button is clicked', () => {
            StationLogs.openCreateModal('st-1');

            document.getElementById('close-log-modal').click();

            expect(document.getElementById('log-entry-modal')).toBeNull();
        });

        it('closes modal when cancel button is clicked', () => {
            StationLogs.openCreateModal('st-1');

            document.getElementById('cancel-log-btn').click();

            expect(document.getElementById('log-entry-modal')).toBeNull();
        });

        it('closes modal when clicking the backdrop', () => {
            StationLogs.openCreateModal('st-1');

            const modal = document.getElementById('log-entry-modal');
            modal.click();

            expect(document.getElementById('log-entry-modal')).toBeNull();
        });
    });

    // ------------------------------------------------------------------ //
    // openDeleteConfirm
    // ------------------------------------------------------------------ //

    describe('openDeleteConfirm', () => {
        it('creates delete confirmation modal with entry title', () => {
            StationLogs.openDeleteConfirm('log-1', 'Important Finding');

            expect(document.getElementById('log-delete-modal')).not.toBeNull();
            expect(document.body.innerHTML).toContain('Delete Journal Entry');
            expect(document.body.innerHTML).toContain('Important Finding');
        });

        it('closes when cancel is clicked', () => {
            StationLogs.openDeleteConfirm('log-1', 'Entry');

            document.getElementById('cancel-delete-btn').click();

            expect(document.getElementById('log-delete-modal')).toBeNull();
        });
    });

    // ------------------------------------------------------------------ //
    // updateFileDisplay
    // ------------------------------------------------------------------ //

    describe('updateFileDisplay', () => {
        it('shows file name and size after selection', () => {
            const fileContainer = document.createElement('div');
            fileContainer.innerHTML = '<div id="log-file-placeholder">Drop file here</div>';

            StationLogs.updateFileDisplay(fileContainer, { name: 'report.pdf', size: 2048 });

            expect(fileContainer.innerHTML).toContain('report.pdf');
            expect(fileContainer.innerHTML).toContain('2.0 KB');
        });

        it('does nothing when placeholder is missing', () => {
            const fileContainer = document.createElement('div');

            expect(() => {
                StationLogs.updateFileDisplay(fileContainer, { name: 'a.txt', size: 100 });
            }).not.toThrow();
        });
    });

    // ------------------------------------------------------------------ //
    // wireUpEntryButtons
    // ------------------------------------------------------------------ //

    describe('wireUpEntryButtons', () => {
        it('wires onclick handlers for edit buttons', () => {
            const wrapper = document.createElement('div');
            wrapper.innerHTML = `
                <button class="edit-log-btn" data-log-id="log-1" data-title="Title" data-notes="Notes"></button>
            `;
            const spy = vi.spyOn(StationLogs, 'openEditModal').mockImplementation(() => {});

            StationLogs.wireUpEntryButtons(wrapper);
            wrapper.querySelector('.edit-log-btn').click();

            expect(spy).toHaveBeenCalledWith('log-1', { title: 'Title', notes: 'Notes' });
            spy.mockRestore();
        });

        it('wires onclick handlers for delete buttons', () => {
            const wrapper = document.createElement('div');
            wrapper.innerHTML = `
                <button class="delete-log-btn" data-log-id="log-2" data-title="Entry"></button>
            `;
            const spy = vi.spyOn(StationLogs, 'openDeleteConfirm').mockImplementation(() => {});

            StationLogs.wireUpEntryButtons(wrapper);
            wrapper.querySelector('.delete-log-btn').click();

            expect(spy).toHaveBeenCalledWith('log-2', 'Entry');
            spy.mockRestore();
        });
    });
});

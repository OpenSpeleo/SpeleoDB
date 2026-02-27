import { StationTags } from './tags.js';
import { API } from '../api.js';
import { State } from '../state.js';
import { Utils } from '../utils.js';
import { Layers } from '../map/layers.js';

vi.mock('../api.js', () => ({
    API: {
        getUserTags: vi.fn(),
        getTagColors: vi.fn(),
        createTag: vi.fn(),
        setStationTag: vi.fn(),
        removeStationTag: vi.fn(),
    },
}));

vi.mock('../state.js', () => ({
    State: {
        userTags: [],
        tagColors: [],
        currentStationForTagging: null,
        allStations: new Map(),
        allSurfaceStations: new Map(),
    },
}));

vi.mock('../utils.js', () => ({
    Utils: {
        showNotification: vi.fn(),
    },
}));

vi.mock('../map/layers.js', () => ({
    Layers: {
        updateStationColor: vi.fn(),
        updateSurfaceStationColor: vi.fn(),
    },
}));

describe('StationTags', () => {
    beforeEach(() => {
        State.userTags = [];
        State.tagColors = [];
        State.currentStationForTagging = null;
        State.allStations = new Map();
        State.allSurfaceStations = new Map();
        document.body.innerHTML = '';
        vi.clearAllMocks();
    });

    // ------------------------------------------------------------------ //
    // loadUserTags
    // ------------------------------------------------------------------ //

    describe('loadUserTags', () => {
        it('sets State.userTags from API response', async () => {
            const tags = [{ id: '1', name: 'Important', color: '#ff0000' }];
            API.getUserTags.mockResolvedValue({ data: tags });

            await StationTags.loadUserTags();

            expect(State.userTags).toEqual(tags);
        });

        it('defaults to empty array when response.data is null', async () => {
            API.getUserTags.mockResolvedValue({ data: null });

            await StationTags.loadUserTags();

            expect(State.userTags).toEqual([]);
        });

        it('sets empty array on API error', async () => {
            API.getUserTags.mockRejectedValue(new Error('Network error'));

            await StationTags.loadUserTags();

            expect(State.userTags).toEqual([]);
        });
    });

    // ------------------------------------------------------------------ //
    // loadTagColors
    // ------------------------------------------------------------------ //

    describe('loadTagColors', () => {
        it('sets State.tagColors from API response', async () => {
            const colors = ['#ff0000', '#00ff00'];
            API.getTagColors.mockResolvedValue({ data: { colors } });

            await StationTags.loadTagColors();

            expect(State.tagColors).toEqual(colors);
        });

        it('uses fallback colors when API fails', async () => {
            API.getTagColors.mockRejectedValue(new Error('fail'));

            await StationTags.loadTagColors();

            expect(State.tagColors).toHaveLength(20);
            expect(State.tagColors[0]).toBe('#ef4444');
        });

        it('uses fallback colors when response.data.colors is missing', async () => {
            API.getTagColors.mockResolvedValue({ data: {} });

            await StationTags.loadTagColors();

            expect(State.tagColors).toHaveLength(20);
        });
    });

    // ------------------------------------------------------------------ //
    // init
    // ------------------------------------------------------------------ //

    describe('init', () => {
        it('loads both tags and colors in parallel', async () => {
            API.getUserTags.mockResolvedValue({ data: [] });
            API.getTagColors.mockResolvedValue({ data: { colors: ['#aaa'] } });

            await StationTags.init();

            expect(API.getUserTags).toHaveBeenCalledTimes(1);
            expect(API.getTagColors).toHaveBeenCalledTimes(1);
        });
    });

    // ------------------------------------------------------------------ //
    // setStationTag
    // ------------------------------------------------------------------ //

    describe('setStationTag', () => {
        it('calls API and updates subsurface station tag', async () => {
            const tag = { id: 'tag-1', name: 'Active', color: '#00ff00' };
            API.setStationTag.mockResolvedValue({ data: tag });
            State.allStations.set('st-1', { id: 'st-1', project: 'proj-1', tag: null });

            await StationTags.setStationTag('st-1', 'tag-1');

            expect(API.setStationTag).toHaveBeenCalledWith('st-1', 'tag-1');
            expect(State.allStations.get('st-1').tag).toEqual(tag);
            expect(Utils.showNotification).toHaveBeenCalledWith('success', 'Tag set on station');
        });

        it('updates surface station tag', async () => {
            const tag = { id: 'tag-1', name: 'Active', color: '#00ff00' };
            API.setStationTag.mockResolvedValue({ data: tag });
            State.allSurfaceStations.set('surf-1', {
                id: 'surf-1', network: 'net-1', station_type: 'surface', tag: null,
            });

            await StationTags.setStationTag('surf-1', 'tag-1');

            expect(State.allSurfaceStations.get('surf-1').tag).toEqual(tag);
        });

        it('shows error notification on failure', async () => {
            API.setStationTag.mockRejectedValue(new Error('API error'));

            await StationTags.setStationTag('st-1', 'tag-1');

            expect(Utils.showNotification).toHaveBeenCalledWith('error', 'API error');
        });
    });

    // ------------------------------------------------------------------ //
    // removeStationTag
    // ------------------------------------------------------------------ //

    describe('removeStationTag', () => {
        it('calls API and clears station tag', async () => {
            API.removeStationTag.mockResolvedValue({});
            State.allStations.set('st-1', {
                id: 'st-1', project: 'proj-1', tag: { id: 'tag-1' },
            });

            await StationTags.removeStationTag('st-1');

            expect(API.removeStationTag).toHaveBeenCalledWith('st-1');
            expect(State.allStations.get('st-1').tag).toBeNull();
            expect(Utils.showNotification).toHaveBeenCalledWith('success', 'Tag removed from station');
        });

        it('shows error notification on failure', async () => {
            API.removeStationTag.mockRejectedValue(new Error('fail'));

            await StationTags.removeStationTag('st-1');

            expect(Utils.showNotification).toHaveBeenCalledWith('error', 'fail');
        });
    });

    // ------------------------------------------------------------------ //
    // updateStationMarkerColor
    // ------------------------------------------------------------------ //

    describe('updateStationMarkerColor', () => {
        it('calls Layers.updateStationColor for subsurface stations', () => {
            const station = { project: 'proj-1', tag: { color: '#ff0000' } };
            State.allStations.set('st-1', station);

            StationTags.updateStationMarkerColor('st-1', station);

            expect(Layers.updateStationColor).toHaveBeenCalledWith('proj-1', 'st-1', '#ff0000');
        });

        it('calls Layers.updateSurfaceStationColor for surface stations', () => {
            const station = { network: 'net-1', station_type: 'surface', tag: { color: '#00ff00' } };
            State.allSurfaceStations.set('surf-1', station);

            StationTags.updateStationMarkerColor('surf-1', station);

            expect(Layers.updateSurfaceStationColor).toHaveBeenCalledWith('net-1', 'surf-1', '#00ff00');
        });

        it('uses default orange when station has no tag', () => {
            const station = { project: 'proj-1', tag: null };
            State.allStations.set('st-1', station);

            StationTags.updateStationMarkerColor('st-1', station);

            expect(Layers.updateStationColor).toHaveBeenCalledWith('proj-1', 'st-1', '#fb923c');
        });

        it('does nothing for non-existent station', () => {
            StationTags.updateStationMarkerColor('nonexistent');

            expect(Layers.updateStationColor).not.toHaveBeenCalled();
            expect(Layers.updateSurfaceStationColor).not.toHaveBeenCalled();
        });
    });

    // ------------------------------------------------------------------ //
    // openTagSelector / closeTagSelector
    // ------------------------------------------------------------------ //

    describe('openTagSelector', () => {
        it('inserts tag selector overlay into DOM', () => {
            State.allStations.set('st-1', { id: 'st-1', tag: null });
            State.userTags = [{ id: 'tag-1', name: 'Important', color: '#ff0000' }];

            StationTags.openTagSelector('st-1');

            expect(document.getElementById('tag-selector-overlay')).not.toBeNull();
        });

        it('does not create overlay for non-existent station', () => {
            StationTags.openTagSelector('nonexistent');

            expect(document.getElementById('tag-selector-overlay')).toBeNull();
        });

        it('marks the current tag with a check indicator', () => {
            State.allStations.set('st-1', { id: 'st-1', tag: { id: 'tag-1' } });
            State.userTags = [{ id: 'tag-1', name: 'Important', color: '#ff0000' }];

            StationTags.openTagSelector('st-1');

            expect(document.getElementById('tag-selector-overlay').innerHTML).toContain('✓ Current');
        });

        it('shows remove-tag button when station already has a tag', () => {
            State.allStations.set('st-1', { id: 'st-1', tag: { id: 'tag-1' } });
            State.userTags = [{ id: 'tag-1', name: 'Active', color: '#00ff00' }];

            StationTags.openTagSelector('st-1');

            expect(document.getElementById('tag-selector-overlay').innerHTML).toContain('Remove Tag from Station');
        });

        it('shows empty-state message when no tags exist', () => {
            State.allStations.set('st-1', { id: 'st-1', tag: null });
            State.userTags = [];

            StationTags.openTagSelector('st-1');

            expect(document.getElementById('tag-selector-overlay').innerHTML).toContain('No tags available');
        });
    });

    describe('closeTagSelector', () => {
        it('removes tag selector overlay', () => {
            document.body.innerHTML = '<div id="tag-selector-overlay"></div>';

            StationTags.closeTagSelector();

            expect(document.getElementById('tag-selector-overlay')).toBeNull();
        });

        it('does nothing if no overlay exists', () => {
            expect(() => StationTags.closeTagSelector()).not.toThrow();
        });
    });

    // ------------------------------------------------------------------ //
    // refreshStationTagDisplay
    // ------------------------------------------------------------------ //

    describe('refreshStationTagDisplay', () => {
        it('renders tag badge when station has a tag', () => {
            document.body.innerHTML = '<div id="station-tag-display"></div>';
            const station = { tag: { name: 'Active', color: '#00ff00' } };
            State.allStations.set('st-1', station);

            StationTags.refreshStationTagDisplay('st-1', station);

            const container = document.getElementById('station-tag-display');
            expect(container.innerHTML).toContain('Active');
            expect(container.innerHTML).toContain('#00ff00');
        });

        it('shows no-tag message when station has no tag', () => {
            document.body.innerHTML = '<div id="station-tag-display"></div>';
            const station = { tag: null };
            State.allStations.set('st-1', station);

            StationTags.refreshStationTagDisplay('st-1', station);

            const container = document.getElementById('station-tag-display');
            expect(container.innerHTML).toContain('No tag assigned');
        });

        it('updates button text to Change Tag when tag exists', () => {
            document.body.innerHTML = `
                <div id="station-tag-display"></div>
                <button id="open-tag-selector-btn"></button>
            `;
            const station = { tag: { name: 'X', color: '#000' } };
            State.allStations.set('st-1', station);

            StationTags.refreshStationTagDisplay('st-1', station);

            expect(document.getElementById('open-tag-selector-btn').textContent).toBe('Change Tag');
        });

        it('updates button text to + Add Tag when no tag', () => {
            document.body.innerHTML = `
                <div id="station-tag-display"></div>
                <button id="open-tag-selector-btn"></button>
            `;
            const station = { tag: null };
            State.allStations.set('st-1', station);

            StationTags.refreshStationTagDisplay('st-1', station);

            expect(document.getElementById('open-tag-selector-btn').textContent).toBe('+ Add Tag');
        });

        it('does nothing if tag container is not in DOM', () => {
            expect(() => StationTags.refreshStationTagDisplay('st-1')).not.toThrow();
        });
    });

    // ------------------------------------------------------------------ //
    // createNewTag
    // ------------------------------------------------------------------ //

    describe('createNewTag', () => {
        it('creates tag via API and adds to State.userTags', async () => {
            const newTag = { id: 'tag-new', name: 'New', color: '#ff0000' };
            API.createTag.mockResolvedValue({ data: newTag });
            State.currentStationForTagging = null;
            document.body.innerHTML = `
                <input id="new-tag-name" value="New" />
                <input id="new-tag-color" value="#ff0000" />
            `;

            await StationTags.createNewTag();

            expect(API.createTag).toHaveBeenCalledWith('New', '#ff0000');
            expect(State.userTags).toContain(newTag);
            expect(Utils.showNotification).toHaveBeenCalledWith('success', expect.stringContaining('New'));
        });

        it('reopens tag selector after creating tag when tagging a station', async () => {
            const newTag = { id: 'tag-new', name: 'New', color: '#ff0000' };
            API.createTag.mockResolvedValue({ data: newTag });
            State.currentStationForTagging = 'st-1';
            State.allStations.set('st-1', { id: 'st-1', tag: null });
            document.body.innerHTML = `
                <input id="new-tag-name" value="New" />
                <input id="new-tag-color" value="#ff0000" />
            `;

            await StationTags.createNewTag();

            expect(document.getElementById('tag-selector-overlay')).not.toBeNull();
        });

        it('shows error for empty tag name', async () => {
            document.body.innerHTML = `
                <input id="new-tag-name" value="  " />
                <input id="new-tag-color" value="#ff0000" />
            `;

            await StationTags.createNewTag();

            expect(API.createTag).not.toHaveBeenCalled();
            expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Please enter a tag name');
        });

        it('shows error for missing color', async () => {
            document.body.innerHTML = `
                <input id="new-tag-name" value="Test" />
                <input id="new-tag-color" value="" />
            `;

            await StationTags.createNewTag();

            expect(API.createTag).not.toHaveBeenCalled();
            expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Please select a color');
        });

        it('shows error notification on API failure', async () => {
            API.createTag.mockRejectedValue(new Error('API error'));
            document.body.innerHTML = `
                <input id="new-tag-name" value="Test" />
                <input id="new-tag-color" value="#ff0000" />
            `;

            await StationTags.createNewTag();

            expect(Utils.showNotification).toHaveBeenCalledWith('error', 'API error');
        });
    });

    // ------------------------------------------------------------------ //
    // selectTagColor
    // ------------------------------------------------------------------ //

    describe('selectTagColor', () => {
        it('sets hidden input value and marks the matching option as selected', () => {
            document.body.innerHTML = `
                <input type="hidden" id="new-tag-color" value="" />
                <input type="color" id="new-tag-custom-color" value="#000" />
                <div class="tag-color-option" data-color="#ff0000"></div>
                <div class="tag-color-option" data-color="#00ff00"></div>
            `;

            StationTags.selectTagColor('#ff0000');

            expect(document.getElementById('new-tag-color').value).toBe('#ff0000');
            expect(document.getElementById('new-tag-custom-color').value).toBe('#ff0000');
            const opts = document.querySelectorAll('.tag-color-option');
            expect(opts[0].classList.contains('selected')).toBe(true);
            expect(opts[1].classList.contains('selected')).toBe(false);
        });
    });
});

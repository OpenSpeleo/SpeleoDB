import type { ModuleMock } from '../../../../../../ts-types/testing/vitest/mocks.ts';
import type { ViewerLandmarkCollection } from '../../../../../../ts-types/domain/map-entities.ts';
import { LandmarkUI } from './ui.ts';

vi.mock('./manager.ts', () => ({
    LandmarkManager: {
        createLandmark: vi.fn(),
        updateLandmark: vi.fn(),
        deleteLandmark: vi.fn(),
    },
}));

vi.mock('../state.ts', () => ({
    State: {
        allLandmarks: new Map(),
        landmarkCollections: new Map(),
    },
}));

vi.mock('../utils.ts', () => {
    const escapeHtml = (text: string | number | null | undefined) => {
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
            safeCssColor: (color: string | null, fallback = '#94a3b8') => (
                /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(String(color || ''))
                    ? color
                    : fallback
            ),
            raw: (html: unknown) => ({ [RAW]: true, value: String(html) }),
            safeHtml: (strings: TemplateStringsArray, ...values: unknown[]) => strings.reduce((r, s, i) => {
                if (i < values.length) {
                    const v = values[i];
                    if (v && typeof v === 'object' && RAW in v) return r + s + (v as unknown as { value: string }).value;
                    return r + s + escapeHtml(v as string);
                }
                return r + s;
            }, ''),
        },
    };
});

vi.mock('../components/modal.ts', () => ({
    Modal: {
        base: vi.fn((id: string, title: string, content: string, footer: string) => `<div id="${id}">${content}${footer}</div>`),
        open: vi.fn((id: string, html: string, cb?: () => void) => {
            document.body.insertAdjacentHTML('beforeend', html);
            if (cb) cb();
        }),
        close: vi.fn(),
    },
}));

import { State } from '../state.ts';

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
        } as ViewerLandmarkCollection);
        State.landmarkCollections.set('personal-1', {
            id: 'personal-1',
            name: 'Personal Landmarks',
            can_write: true,
            is_personal: true,
        } as ViewerLandmarkCollection);

        LandmarkUI.openCreateModal([6, 46]);

        const select = (document.getElementById('landmark-collection') as HTMLSelectElement);
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
        } as ViewerLandmarkCollection);
        State.landmarkCollections.set('personal-1', {
            id: 'personal-1',
            name: 'Personal Landmarks',
            color: '#222222',
            can_write: true,
            is_personal: true,
        } as ViewerLandmarkCollection);

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
        expect(groups[0]!.id).toBe('personal-1');
        expect(groups[0]!.label).toBe('Personal Landmarks (Private)');
        expect(groups[0]!.color).toBe('#222222');
        expect(groups[1]!.canWrite).toBe(false);
    });

    it('renders landmark manager collection groups collapsed by default', () => {
        document.body.innerHTML = '<div id="landmark-manager-content"></div><div id="landmark-manager-modal"></div>';
        State.landmarkCollections.set('shared-1', {
            id: 'shared-1',
            name: 'Shared',
            color: '#111111',
            can_write: false,
            is_personal: false,
        } as ViewerLandmarkCollection);
        State.landmarkCollections.set('personal-1', {
            id: 'personal-1',
            name: 'Personal Landmarks',
            color: '#222222',
            can_write: true,
            is_personal: true,
        } as ViewerLandmarkCollection);
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
        expect(groups[0]!.hasAttribute('open')).toBe(false);
        expect(groups[1]!.hasAttribute('open')).toBe(false);
        expect(groups[0]!.querySelector('.landmark-collection-toggle-icon')).not.toBeNull();
        expect(groups[0]!.querySelector('summary')!.title).toBe('Expand or collapse collection group');
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

        expect((document.getElementById('edit-landmark-btn') as HTMLElement)).toBeNull();
        expect((document.getElementById('delete-landmark-btn') as HTMLElement)).toBeNull();
        expect(document.body.innerHTML).not.toContain('disabled');
    });
});

import { LandmarkManager as originalLandmarkManager } from './manager.ts';
import { Utils as originalUtils } from '../utils.ts';
import { Modal as originalModal } from '../components/modal.ts';
import { goToLandmark as originalGoToLandmark } from '../map/navigation.ts';
vi.mock('../map/navigation.ts', () => ({ goToLandmark: vi.fn() }));

describe('LandmarkUI form lifecycle', () => {
    beforeEach(() => { vi.clearAllMocks(); document.body.innerHTML = ''; State.allLandmarks.clear(); State.landmarkCollections.clear(); });
    afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ''; });
    function field(id: string, value: string) { (document.getElementById(id) as HTMLInputElement).value = value; }
    async function submit(id: string) { return (document.getElementById(id) as HTMLFormElement).onsubmit!(new Event('submit') as SubmitEvent) as unknown; }
    it('keeps create coordinates and the null collection, trims text and opens details through the same receiver', async () => {
        const details = vi.spyOn(LandmarkUI, 'openDetailsModal').mockImplementation(() => {});
        LandmarkManager.createLandmark.mockResolvedValue({ id: 'created' });
        LandmarkUI.openCreateModal(['6.5', '46.5']);
        expect((document.getElementById('create-landmark-form') as HTMLFormElement).onsubmit!.constructor.name).toBe('AsyncFunction');
        await submit('create-landmark-form'); expect(LandmarkManager.createLandmark).not.toHaveBeenCalled();
        field('landmark-name', '  Place  '); field('landmark-description', '  Note  '); await submit('create-landmark-form');
        expect(LandmarkManager.createLandmark).toHaveBeenCalledWith({ name: 'Place', description: 'Note', collection: null, latitude: '46.5', longitude: '6.5' });
        expect(details).toHaveBeenCalledWith('created', true); expect(details.mock.contexts[0]).toBe(LandmarkUI);
        expect(Modal.close).toHaveBeenCalledWith('create-landmark-modal');
    });
    it.each([['', '0', '0', 'Please enter a landmark name.'], ['Name', '91', '0', 'Latitude'], ['Name', '0', '-181', 'Longitude']])('validates manual fields (%s,%s,%s)', async (name, lat, lon, error) => {
        LandmarkUI.openCreateModalManual(); field('landmark-name-manual', name); field('landmark-latitude-manual', lat); field('landmark-longitude-manual', lon);
        await submit('create-landmark-manual-form'); expect(LandmarkManager.createLandmark).not.toHaveBeenCalled();
        expect((document.getElementById('landmark-coord-error') as HTMLElement).textContent).toContain(error);
    });
    it('creates manual coordinates as numbers and closes before camera navigation', async () => {
        LandmarkManager.createLandmark.mockResolvedValue({ id: 'new' }); LandmarkUI.openCreateModalManual();
        field('landmark-name-manual', 'Place'); field('landmark-latitude-manual', '46.5'); field('landmark-longitude-manual', '6.5');
        await submit('create-landmark-manual-form');
        expect(LandmarkManager.createLandmark).toHaveBeenCalledWith(expect.objectContaining({ latitude: 46.5, longitude: 6.5, collection: null }));
        expect(goToLandmark).toHaveBeenCalledWith('new', 46.5, 6.5);
        expect(Modal.close.mock.invocationCallOrder[0]!).toBeLessThan(goToLandmark.mock.invocationCallOrder[0]!);
    });
    it('updates writable landmarks and preserves separate edit and detail closes', async () => {
        State.allLandmarks.set('lm', { id: 'lm', name: 'Old', latitude: 1, longitude: 2, can_write: true });
        LandmarkUI.openEditModal('lm'); field('edit-landmark-name', '  New  ');
        await submit('edit-landmark-form');
        expect(LandmarkManager.updateLandmark).toHaveBeenCalledWith('lm', { name: 'New', description: '', latitude: 1, longitude: 2, collection: null });
        expect(Modal.close.mock.calls).toEqual([['edit-landmark-modal'], ['landmark-details-modal']]);
        expect(goToLandmark).toHaveBeenCalledWith('lm', 1, 2);
    });
    it('contains errors at each form and keeps the generic delete failure message', async () => {
        LandmarkManager.createLandmark.mockRejectedValueOnce({ message: 'Create denied' });
        LandmarkUI.openCreateModal([1, 2]); field('landmark-name', 'Place'); await submit('create-landmark-form');
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Create denied');
        LandmarkManager.deleteLandmark.mockRejectedValueOnce({ message: 'Private server message' });
        LandmarkUI.showDeleteConfirmModal({ id: 'lm', name: 'Place', can_delete: true });
        await (document.getElementById('confirm-delete-landmark') as HTMLElement).onclick!(new MouseEvent("click") as PointerEvent);
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Failed to delete Landmark');
        expect(Modal.close).not.toHaveBeenCalled();
    });
    it('preserves missing landmark branches and independent write/delete permissions', () => {
        LandmarkUI.openEditModal('missing'); expect(Utils.showNotification).not.toHaveBeenCalled();
        LandmarkUI.openDetailsModal('missing'); expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Landmark not found');
        LandmarkUI.showDeleteConfirmModal({ id: 'lm', can_delete: false });
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'This collection Landmark is read-only for you.');
        State.allLandmarks.set('lm', { id: 'lm', name: 'Place', can_write: false, can_delete: true });
        LandmarkUI.openDetailsModal('lm'); expect((document.getElementById('edit-landmark-btn') as HTMLElement)).toBeNull(); expect((document.getElementById('delete-landmark-btn') as HTMLElement)).not.toBeNull();
    });
});

const LandmarkManager = originalLandmarkManager as unknown as ModuleMock<typeof originalLandmarkManager>;

const Utils = originalUtils as unknown as ModuleMock<typeof originalUtils>;

const Modal = originalModal as unknown as ModuleMock<typeof originalModal>;

const goToLandmark = vi.mocked(originalGoToLandmark);

import type { ApplicationUrls } from '../../../../../ts-types/browser/urls.d.ts';
import type { LandmarkFormCollection } from '../../../../../ts-types/domain/landmark-forms.ts';
import type { ViewerLandmark } from '../../../../../ts-types/domain/map-entities.ts';
import type { ModuleMock } from '../../../../../ts-types/testing/vitest/mocks.ts';
vi.mock('../map_viewer/landmarks/forms.ts', () => ({
    LandmarkForms: {
        openLandmarkCreateModal: vi.fn(),
        openLandmarkEditModal: vi.fn(),
        openLandmarkDeleteModal: vi.fn(),
        openLandmarkBulkTransferModal: vi.fn(),
        openLandmarkBulkDeleteModal: vi.fn(),
    },
}));

vi.mock('../map_viewer/utils.ts', () => ({
    Utils: {
        getCSRFToken: vi.fn(() => 'test-csrf'),
        showNotification: vi.fn(),
        copyToClipboard: vi.fn(),
    },
}));

import { initLandmarkCollectionDetails } from './details_main.ts';
import { LandmarkForms as forms } from '../map_viewer/landmarks/forms.ts';
import { Utils as utilities } from '../map_viewer/utils.ts';

function buildPageHtml({ canWrite = true, landmarks = [] }: { canWrite?: boolean; landmarks?: ViewerLandmark[] } = {}) {
    const landmarkRows = landmarks.map(lm => `
        <tr class="landmark-row" data-landmark-id="${lm.id}">
            ${canWrite ? `<td><input type="checkbox" class="landmark-row-select" data-landmark-id="${lm.id}"></td>` : ''}
            <td>${lm.name}</td>
            <td class="landmark-coord-cell" data-coord="${lm.longitude}">${lm.longitude}</td>
            <td class="landmark-coord-cell" data-coord="${lm.latitude}">${lm.latitude}</td>
            <td>${lm.created_by}</td>
            <td>
                <a class="landmark-action-btn locate landmark-locate-btn" href="/map?goto=${lm.latitude},${lm.longitude}"></a>
                ${canWrite ? `
                    <button class="landmark-edit-btn" data-landmark-id="${lm.id}"></button>
                    <button class="landmark-delete-btn" data-landmark-id="${lm.id}"></button>
                ` : ''}
            </td>
        </tr>
    `).join('');

    return `
        ${canWrite ? '<button id="add-landmark-btn">New</button>' : ''}
        <table id="collection_landmarks_table">
            <thead><tr>
                ${canWrite ? '<th><input type="checkbox" id="collection_landmarks_table_select_all"></th>' : ''}
                <th>Name</th><th>Lon</th><th>Lat</th><th>By</th><th>Actions</th>
            </tr></thead>
            <tbody id="collection_landmarks_table_body">${landmarkRows}</tbody>
        </table>
        ${canWrite ? `
        <div id="landmarks-bulk-action-bar" hidden>
            <span id="landmarks-selection-count">0</span>
            <button id="landmarks-bulk-transfer-btn"></button>
            <button id="landmarks-bulk-delete-btn"></button>
            <button id="landmarks-bulk-clear-btn"></button>
        </div>
        ` : ''}
        <script type="application/json" id="landmark_collection_context">${JSON.stringify({
            id: 'col-1', name: 'Test Col', color: '#aabbcc', is_personal: false,
        })}</script>
        <script type="application/json" id="landmark_table_data">${JSON.stringify(
            landmarks.map(lm => ({
                id: lm.id, name: lm.name, description: '', latitude: String(lm.latitude),
                longitude: String(lm.longitude), created_by: lm.created_by, collection: 'col-1',
            }))
        )}</script>
    `;
}

const SAMPLE_LANDMARKS = [
    { id: 'lm-1', name: 'Alpha', latitude: 45, longitude: -122, created_by: 'a@x.com' },
    { id: 'lm-2', name: 'Beta', latitude: 46, longitude: -123, created_by: 'b@x.com' },
    { id: 'lm-3', name: 'Gamma', latitude: 47, longitude: -124, created_by: 'c@x.com' },
];

describe('initLandmarkCollectionDetails', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.clearAllMocks();
        window.LANDMARK_DETAILS_CONTEXT = { canWrite: true };
        window.$ = undefined;
        window.Urls = {
            'api:v2:landmark-collections': () => '/api/v2/landmark-collections/',
        } as ApplicationUrls;
        global.fetch = vi.fn(() => Promise.resolve({
            ok: true,
            json: () => Promise.resolve([]),
        } as Response)) as unknown as typeof fetch;
    });

    it('returns early when collection context is missing', () => {
        document.body.innerHTML = '<div>empty page</div>';
        initLandmarkCollectionDetails();

        expect(document.querySelector<HTMLElement>('#landmarks-bulk-action-bar')!).toBeNull();
    });

    it('hydrates landmarks from inline JSON', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const checkboxes = document.querySelectorAll('.landmark-row-select');
        expect(checkboxes.length).toBe(3);
    });

    it('hides bulk bar when nothing is selected', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const bar = document.querySelector<HTMLElement>('#landmarks-bulk-action-bar')!;
        expect(bar.hasAttribute('hidden')).toBe(true);
    });

    it('shows bulk bar when a row checkbox is toggled', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const cb = document.querySelector<HTMLInputElement>('.landmark-row-select[data-landmark-id="lm-1"]')!;
        cb.checked = true;
        cb.onchange!(new Event("change"));

        const bar = document.querySelector<HTMLElement>('#landmarks-bulk-action-bar')!;
        expect(bar.hasAttribute('hidden')).toBe(false);

        const count = document.querySelector<HTMLElement>('#landmarks-selection-count')!;
        expect(count.textContent).toBe('1');
    });

    it('select-all checks all row checkboxes', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const selectAll = document.querySelector<HTMLInputElement>('#collection_landmarks_table_select_all')!;
        selectAll.checked = true;
        selectAll.dispatchEvent(new Event('change'));

        const checked = document.querySelectorAll('.landmark-row-select:checked');
        expect(checked.length).toBe(3);

        const count = document.querySelector<HTMLElement>('#landmarks-selection-count')!;
        expect(count.textContent).toBe('3');
    });

    it('clear button empties selection and hides bar', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const cb = document.querySelector<HTMLInputElement>('.landmark-row-select[data-landmark-id="lm-1"]')!;
        cb.checked = true;
        cb.onchange!(new Event("change"));

        const clearBtn = document.querySelector<HTMLElement>('#landmarks-bulk-clear-btn')!;
        clearBtn.onclick!(new MouseEvent("click") as PointerEvent);

        const bar = document.querySelector<HTMLElement>('#landmarks-bulk-action-bar')!;
        expect(bar.hasAttribute('hidden')).toBe(true);

        const checked = document.querySelectorAll('.landmark-row-select:checked');
        expect(checked.length).toBe(0);
    });

    it('bulk transfer button opens transfer modal with selected landmarks', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const first = document.querySelector<HTMLInputElement>('.landmark-row-select[data-landmark-id="lm-1"]')!;
        const third = document.querySelector<HTMLInputElement>('.landmark-row-select[data-landmark-id="lm-3"]')!;
        first.checked = true;
        third.checked = true;
        first.onchange!(new Event("change"));
        third.onchange!(new Event("change"));

        const transferBtn = document.querySelector<HTMLElement>('#landmarks-bulk-transfer-btn')!;
        transferBtn.onclick!(new MouseEvent("click") as PointerEvent);

        expect(LandmarkForms.openLandmarkBulkTransferModal).toHaveBeenCalledTimes(1);
        const call = LandmarkForms.openLandmarkBulkTransferModal.mock.calls[0]![0]!;
        expect((call.sourceCollection as LandmarkFormCollection).id).toBe('col-1');
        expect(call.landmarks!.map(lm => lm.id)).toEqual(['lm-1', 'lm-3']);
    });

    it('bulk delete button opens delete modal with selected landmarks', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const second = document.querySelector<HTMLInputElement>('.landmark-row-select[data-landmark-id="lm-2"]')!;
        second.checked = true;
        second.onchange!(new Event("change"));

        const deleteBtn = document.querySelector<HTMLElement>('#landmarks-bulk-delete-btn')!;
        deleteBtn.onclick!(new MouseEvent("click") as PointerEvent);

        expect(LandmarkForms.openLandmarkBulkDeleteModal).toHaveBeenCalledTimes(1);
        const call = LandmarkForms.openLandmarkBulkDeleteModal.mock.calls[0]![0]!;
        expect((call.sourceCollection as LandmarkFormCollection).id).toBe('col-1');
        expect(call.landmarks!.map(lm => lm.id)).toEqual(['lm-2']);
    });

    it('edit button opens edit modal via LandmarkForms', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const editBtn = document.querySelector<HTMLElement>('.landmark-edit-btn[data-landmark-id="lm-1"]')!;
        editBtn.onclick!(new MouseEvent('click') as PointerEvent);

        expect(LandmarkForms.openLandmarkEditModal).toHaveBeenCalledTimes(1);
        const call = LandmarkForms.openLandmarkEditModal.mock.calls[0]![0]!;
        expect(call.landmark!.id).toBe('lm-1');
    });

    it('delete button opens delete modal via LandmarkForms', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const deleteBtn = document.querySelector<HTMLElement>('.landmark-delete-btn[data-landmark-id="lm-2"]')!;
        deleteBtn.onclick!(new MouseEvent('click') as PointerEvent);

        expect(LandmarkForms.openLandmarkDeleteModal).toHaveBeenCalledTimes(1);
        const call = LandmarkForms.openLandmarkDeleteModal.mock.calls[0]![0]!;
        expect(call.landmark!.id).toBe('lm-2');
    });

    it('add button opens create modal via LandmarkForms', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const addBtn = document.querySelector<HTMLElement>('#add-landmark-btn')!;
        addBtn.onclick!(new MouseEvent("click") as PointerEvent);

        expect(LandmarkForms.openLandmarkCreateModal).toHaveBeenCalledTimes(1);
        const call = LandmarkForms.openLandmarkCreateModal.mock.calls[0]![0]!;
        expect(call.lockedCollectionId).toBe('col-1');
    });

    it('coordinate cell copies value on click', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const coordCell = document.querySelector<HTMLElement>('.landmark-coord-cell')!;
        coordCell.click();

        expect(Utils.copyToClipboard).toHaveBeenCalled();
    });

    it('does not render checkboxes or bulk bar for read-only users', () => {
        window.LANDMARK_DETAILS_CONTEXT = { canWrite: false };
        document.body.innerHTML = buildPageHtml({ canWrite: false, landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        expect(document.querySelectorAll('.landmark-row-select').length).toBe(0);
        expect(document.querySelector<HTMLElement>('#landmarks-bulk-action-bar')!).toBeNull();
    });

    it('is-selected class toggles with checkbox', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const cb = document.querySelector<HTMLInputElement>('.landmark-row-select[data-landmark-id="lm-1"]')!;
        const row = cb.closest('tr')!;

        cb.checked = true;
        cb.onchange!(new Event("change"));
        expect(row.classList.contains('is-selected')).toBe(true);

        cb.checked = false;
        cb.onchange!(new Event("change"));
        expect(row.classList.contains('is-selected')).toBe(false);
    });
});

describe('collection initialization boundaries', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        window.LANDMARK_DETAILS_CONTEXT = { canWrite: true };
        window.$ = undefined;
        window.Urls = { 'api:v2:landmark-collections': () => '/collections/' } as ApplicationUrls;
        global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] }) as unknown as typeof fetch;
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
    });
    it('logs malformed context and returns before table or collection initialization', () => {
        const error = vi.spyOn(console, 'error').mockImplementation(() => {});
        document.getElementById('landmark_collection_context')!.textContent = '{';
        expect(initLandmarkCollectionDetails()).toBeUndefined();
        expect(error).toHaveBeenCalledWith('Failed to parse inline JSON #landmark_collection_context:', expect.any(SyntaxError));
        expect(fetch).not.toHaveBeenCalled(); error.mockRestore();
    });
    it('normalizes fetched identifiers and permissions for the shared create form without replacing the locked source', async () => {
        global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [{ id: 4, name: 'Target', user_permission_level: 2 }] }) as unknown as typeof fetch;
        initLandmarkCollectionDetails(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
        document.getElementById('add-landmark-btn')!.click();
        expect(fetch).toHaveBeenCalledWith('/collections/', { method: 'GET', credentials: 'same-origin', headers: { 'X-CSRFToken': 'test-csrf' } });
        expect(LandmarkForms.openLandmarkCreateModal).toHaveBeenCalledWith(expect.objectContaining({ lockedCollectionId: 'col-1', collections: [{ id: '4', name: 'Target', user_permission_level: 2, can_write: true, can_admin: false }] }));
    });
    it('restores selected checkboxes after DataTables redraw and resets selection on reinitialization', () => {
        let draw!: () => void;
        const table = { on: vi.fn((event: string, callback: () => void) => { draw = callback; }) };
        const DataTable = vi.fn(() => table);
        window.$ = vi.fn(() => ({ length: 1, DataTable })) as unknown as JQueryStatic;
        initLandmarkCollectionDetails();
        const checkbox = document.querySelector<HTMLInputElement>('.landmark-row-select')!; checkbox.checked = true; checkbox.onchange!(new Event("change"));
        checkbox.checked = false; draw(); expect(checkbox.checked).toBe(true);
        expect(DataTable).toHaveBeenCalledWith(expect.objectContaining({ order: [[1, 'asc']], searching: false, ordering: true, paging: false, info: false }));
        initLandmarkCollectionDetails(); expect(checkbox.checked).toBe(false);
        expect(document.getElementById('landmarks-bulk-action-bar')!.hidden).toBe(true);
    });
    it('retains duplicate coordinate listeners across repeated initialization', () => {
        initLandmarkCollectionDetails(); initLandmarkCollectionDetails();
        document.querySelector<HTMLElement>('.landmark-coord-cell')!.click();
        expect(Utils.copyToClipboard).toHaveBeenCalledTimes(2);
    });
});

const LandmarkForms = forms as unknown as ModuleMock<typeof forms>;
const Utils = utilities as unknown as ModuleMock<typeof utilities>;

vi.mock('../map_viewer/landmarks/forms.js', () => ({
    LandmarkForms: {
        openLandmarkCreateModal: vi.fn(),
        openLandmarkEditModal: vi.fn(),
        openLandmarkDeleteModal: vi.fn(),
        openLandmarkBulkTransferModal: vi.fn(),
        openLandmarkBulkDeleteModal: vi.fn(),
    },
}));

vi.mock('../map_viewer/utils.js', () => ({
    Utils: {
        getCSRFToken: vi.fn(() => 'test-csrf'),
        showNotification: vi.fn(),
        copyToClipboard: vi.fn(),
    },
}));

import { initLandmarkCollectionDetails } from './details_main.js';
import { LandmarkForms } from '../map_viewer/landmarks/forms.js';
import { Utils } from '../map_viewer/utils.js';

function buildPageHtml({ canWrite = true, landmarks = [] } = {}) {
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
        };
        global.fetch = vi.fn(() => Promise.resolve({
            ok: true,
            json: () => Promise.resolve([]),
        }));
    });

    it('returns early when collection context is missing', () => {
        document.body.innerHTML = '<div>empty page</div>';
        initLandmarkCollectionDetails();

        expect(document.querySelector('#landmarks-bulk-action-bar')).toBeNull();
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

        const bar = document.querySelector('#landmarks-bulk-action-bar');
        expect(bar.hasAttribute('hidden')).toBe(true);
    });

    it('shows bulk bar when a row checkbox is toggled', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const cb = document.querySelector('.landmark-row-select[data-landmark-id="lm-1"]');
        cb.checked = true;
        cb.onchange();

        const bar = document.querySelector('#landmarks-bulk-action-bar');
        expect(bar.hasAttribute('hidden')).toBe(false);

        const count = document.querySelector('#landmarks-selection-count');
        expect(count.textContent).toBe('1');
    });

    it('select-all checks all row checkboxes', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const selectAll = document.querySelector('#collection_landmarks_table_select_all');
        selectAll.checked = true;
        selectAll.dispatchEvent(new Event('change'));

        const checked = document.querySelectorAll('.landmark-row-select:checked');
        expect(checked.length).toBe(3);

        const count = document.querySelector('#landmarks-selection-count');
        expect(count.textContent).toBe('3');
    });

    it('clear button empties selection and hides bar', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const cb = document.querySelector('.landmark-row-select[data-landmark-id="lm-1"]');
        cb.checked = true;
        cb.onchange();

        const clearBtn = document.querySelector('#landmarks-bulk-clear-btn');
        clearBtn.onclick();

        const bar = document.querySelector('#landmarks-bulk-action-bar');
        expect(bar.hasAttribute('hidden')).toBe(true);

        const checked = document.querySelectorAll('.landmark-row-select:checked');
        expect(checked.length).toBe(0);
    });

    it('bulk transfer button opens transfer modal with selected landmarks', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const first = document.querySelector('.landmark-row-select[data-landmark-id="lm-1"]');
        const third = document.querySelector('.landmark-row-select[data-landmark-id="lm-3"]');
        first.checked = true;
        third.checked = true;
        first.onchange();
        third.onchange();

        const transferBtn = document.querySelector('#landmarks-bulk-transfer-btn');
        transferBtn.onclick();

        expect(LandmarkForms.openLandmarkBulkTransferModal).toHaveBeenCalledTimes(1);
        const call = LandmarkForms.openLandmarkBulkTransferModal.mock.calls[0][0];
        expect(call.sourceCollection.id).toBe('col-1');
        expect(call.landmarks.map(lm => lm.id)).toEqual(['lm-1', 'lm-3']);
    });

    it('bulk delete button opens delete modal with selected landmarks', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const second = document.querySelector('.landmark-row-select[data-landmark-id="lm-2"]');
        second.checked = true;
        second.onchange();

        const deleteBtn = document.querySelector('#landmarks-bulk-delete-btn');
        deleteBtn.onclick();

        expect(LandmarkForms.openLandmarkBulkDeleteModal).toHaveBeenCalledTimes(1);
        const call = LandmarkForms.openLandmarkBulkDeleteModal.mock.calls[0][0];
        expect(call.sourceCollection.id).toBe('col-1');
        expect(call.landmarks.map(lm => lm.id)).toEqual(['lm-2']);
    });

    it('edit button opens edit modal via LandmarkForms', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const editBtn = document.querySelector('.landmark-edit-btn[data-landmark-id="lm-1"]');
        editBtn.onclick(new MouseEvent('click'));

        expect(LandmarkForms.openLandmarkEditModal).toHaveBeenCalledTimes(1);
        const call = LandmarkForms.openLandmarkEditModal.mock.calls[0][0];
        expect(call.landmark.id).toBe('lm-1');
    });

    it('delete button opens delete modal via LandmarkForms', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const deleteBtn = document.querySelector('.landmark-delete-btn[data-landmark-id="lm-2"]');
        deleteBtn.onclick(new MouseEvent('click'));

        expect(LandmarkForms.openLandmarkDeleteModal).toHaveBeenCalledTimes(1);
        const call = LandmarkForms.openLandmarkDeleteModal.mock.calls[0][0];
        expect(call.landmark.id).toBe('lm-2');
    });

    it('add button opens create modal via LandmarkForms', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const addBtn = document.querySelector('#add-landmark-btn');
        addBtn.onclick();

        expect(LandmarkForms.openLandmarkCreateModal).toHaveBeenCalledTimes(1);
        const call = LandmarkForms.openLandmarkCreateModal.mock.calls[0][0];
        expect(call.lockedCollectionId).toBe('col-1');
    });

    it('coordinate cell copies value on click', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const coordCell = document.querySelector('.landmark-coord-cell');
        coordCell.click();

        expect(Utils.copyToClipboard).toHaveBeenCalled();
    });

    it('does not render checkboxes or bulk bar for read-only users', () => {
        window.LANDMARK_DETAILS_CONTEXT = { canWrite: false };
        document.body.innerHTML = buildPageHtml({ canWrite: false, landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        expect(document.querySelectorAll('.landmark-row-select').length).toBe(0);
        expect(document.querySelector('#landmarks-bulk-action-bar')).toBeNull();
    });

    it('is-selected class toggles with checkbox', () => {
        document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
        initLandmarkCollectionDetails();

        const cb = document.querySelector('.landmark-row-select[data-landmark-id="lm-1"]');
        const row = cb.closest('tr');

        cb.checked = true;
        cb.onchange();
        expect(row.classList.contains('is-selected')).toBe(true);

        cb.checked = false;
        cb.onchange();
        expect(row.classList.contains('is-selected')).toBe(false);
    });
});

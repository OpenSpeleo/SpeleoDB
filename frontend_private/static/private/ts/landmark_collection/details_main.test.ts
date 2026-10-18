import type { ViewerLandmark } from '../../../../../ts-types/domain/map-entities.ts';
import { startApiServer, setBrowserUrl } from '../../../../../frontend_common/test/api-server.ts';
import { initLandmarkCollectionDetails } from './details_main.ts';

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

let server: Awaited<ReturnType<typeof startApiServer>>;
beforeAll(async () => { server = await startApiServer(); });
afterAll(async () => { await server.close(); });
beforeEach(() => {
    server.reset();
    server.reply({ json: [] });
    setBrowserUrl(server.origin);
    window.LANDMARK_DETAILS_CONTEXT = { canWrite: true };
    document.body.innerHTML = buildPageHtml({ landmarks: SAMPLE_LANDMARKS });
});
afterEach(async () => {
    // The page intentionally starts its collection read without blocking initial rendering.
    if (window.LANDMARK_DETAILS_CONTEXT?.canWrite && document.getElementById('landmark_collection_context')) await vi.waitFor(() => { expect(server.requests.length).toBeGreaterThan(0); });
    await new Promise(resolve => setTimeout(resolve, 20));
    document.body.replaceChildren();
});

it('returns early without valid collection context and makes no request', () => {
    document.body.innerHTML = '<div>empty page</div>';
    initLandmarkCollectionDetails();
    expect(server.requests).toHaveLength(0);
    expect(document.getElementById('landmarks-bulk-action-bar')).toBeNull();
});

it('hydrates inline records and maintains row selection, select all, and clear state', () => {
    initLandmarkCollectionDetails();
    expect(document.querySelectorAll('.landmark-row-select')).toHaveLength(3);
    const checkbox = document.querySelector<HTMLInputElement>('.landmark-row-select')!;
    checkbox.click();
    expect(checkbox.closest('tr')!.classList.contains('is-selected')).toBe(true);
    expect(document.getElementById('landmarks-selection-count')!.textContent).toBe('1');
    expect(document.getElementById('landmarks-bulk-action-bar')!.hidden).toBe(false);
    document.getElementById('collection_landmarks_table_select_all')!.click();
    expect(document.querySelectorAll('.landmark-row-select:checked')).toHaveLength(3);
    document.getElementById('landmarks-bulk-clear-btn')!.click();
    expect(document.querySelectorAll('.landmark-row-select:checked')).toHaveLength(0);
    expect(document.getElementById('landmarks-bulk-action-bar')!.hidden).toBe(true);
});

it('opens real create/edit/delete dialogs with the source collection and chosen record', async () => {
    initLandmarkCollectionDetails();
    document.getElementById('add-landmark-btn')!.click();
    expect(document.querySelector<HTMLInputElement>('#landmark-create-form-collection')!.value).toBe('col-1');
    expect(document.getElementById('create-landmark-modal')!.textContent).toContain('Test Col');
    document.querySelector<HTMLElement>('.landmark-edit-btn[data-landmark-id="lm-1"]')!.click();
    expect(document.querySelector<HTMLInputElement>('#landmark-edit-form-name')!.value).toBe('Alpha');
    document.querySelector<HTMLElement>('.landmark-delete-btn[data-landmark-id="lm-2"]')!.click();
    expect(document.getElementById('delete-landmark-modal')!.textContent).toContain('Beta');
    await vi.waitFor(() => { expect(server.requests).toHaveLength(1); });
});

it('normalizes generated collection permissions before showing transfer destinations', async () => {
    server.reply({ json: [{ id: 'target', name: 'Target', user_permission_level: 2 }] });
    initLandmarkCollectionDetails();
    await vi.waitFor(() => { expect(server.requests).toHaveLength(1); });
    await new Promise(resolve => setTimeout(resolve, 20));
    document.querySelector<HTMLElement>('.landmark-row-select')!.click();
    document.getElementById('landmarks-bulk-transfer-btn')!.click();
    const selector = document.querySelector<HTMLSelectElement>('#bulk-transfer-target')!;
    expect(selector.value).toBe('target');
    expect(selector.textContent).toContain('Target');
    expect(server.requests[0]).toMatchObject({ method: 'GET', path: '/api/v2/landmark-collections/' });
});

it('opens real bulk deletion for only the selected records', () => {
    initLandmarkCollectionDetails();
    document.querySelector<HTMLElement>('.landmark-row-select[data-landmark-id="lm-2"]')!.click();
    document.getElementById('landmarks-bulk-delete-btn')!.click();
    const modal = document.getElementById('bulk-delete-landmark-modal')!;
    expect(modal.textContent).toContain('Beta');
    expect(modal.textContent).not.toContain('Alpha');
});

it('does not expose edit or selection controls to read-only users', () => {
    window.LANDMARK_DETAILS_CONTEXT = { canWrite: false };
    document.body.innerHTML = buildPageHtml({ canWrite: false, landmarks: SAMPLE_LANDMARKS });
    initLandmarkCollectionDetails();
    expect(document.querySelectorAll('.landmark-row-select')).toHaveLength(0);
    expect(document.getElementById('landmarks-bulk-action-bar')).toBeNull();
    expect(document.getElementById('add-landmark-btn')).toBeNull();
});

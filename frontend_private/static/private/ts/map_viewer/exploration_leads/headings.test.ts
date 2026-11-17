// @vitest-environment node

import { once } from 'node:events';
import { createServer } from 'node:http';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { JSDOM } from 'jsdom';
import { Config } from '../config.ts';
import { State } from '../state.ts';
import { ExplorationLeadManager } from './manager.ts';
import { Modal } from '../components/modal.ts';

let ExplorationLeadUI: typeof import('./ui.ts')['ExplorationLeadUI'];
let server: Server;
let dom: JSDOM;
let globals: Map<string, PropertyDescriptor | undefined>;
let lead: ReturnType<typeof initialLead>;
let allowWrites: boolean;
let requests: { method: string; body: Record<string, unknown> }[];

function uncheckedDirections(headings: number[]) {
    return (headings.length ? headings : [null]).map(heading => ({ heading, checked: false }));
}

function initialLead() {
    return {
        id: 'lead', project: 'project', latitude: '46.5', longitude: '6.5',
        description: '  Original !N!\nFull comment  ', directions: uncheckedDirections([0, 90]),
        created_by: 'surveyor@example.test', creation_date: '2026-01-01T00:00:00Z',
        modified_date: '2026-01-01T00:00:00Z',
    };
}

beforeEach(async () => {
    lead = initialLead();
    requests = [];
    allowWrites = true;
    server = createServer((request, response) => {
        void (async () => {
            const chunks: Uint8Array[] = [];
            for await (const chunk of request as AsyncIterable<Uint8Array>) chunks.push(chunk);
            const body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) as Record<string, unknown> : {};
            requests.push({ method: request.method!, body });
            response.setHeader('Content-Type', 'application/json');
            if (request.method === 'GET') {
                response.end(JSON.stringify({ type: 'FeatureCollection', features: [{
                    type: 'Feature', id: lead.id,
                    geometry: { type: 'Point', coordinates: [Number(lead.longitude), Number(lead.latitude)] },
                    properties: lead,
                }] }));
            } else if (!allowWrites) {
                response.statusCode = 403;
                response.end(JSON.stringify({ detail: 'Project write permission revoked.' }));
            } else {
                Object.assign(lead, body);
                response.statusCode = request.method === 'POST' ? 201 : 200;
                response.end(JSON.stringify(lead));
            }
        })().catch((error: unknown) => response.destroy(error instanceof Error ? error : new Error(String(error))));
    });
    server.listen(0, '127.0.0.1');
    await once(server, 'listening');
    dom = new JSDOM('<div id="map-viewer-shell"></div>', {
        url: `http://127.0.0.1:${(server.address() as AddressInfo).port}/`,
        pretendToBeVisual: true,
    });
    globals = new Map(['window', 'document', 'HTMLElement', 'HTMLInputElement', 'Element', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame'].map(name => [
        name, Object.getOwnPropertyDescriptor(globalThis, name),
    ]));
    Object.assign(globalThis, {
        window: dom.window, document: dom.window.document,
        HTMLElement: dom.window.HTMLElement, HTMLInputElement: dom.window.HTMLInputElement, Element: dom.window.Element,
        getComputedStyle: dom.window.getComputedStyle,
        requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window),
        cancelAnimationFrame: dom.window.cancelAnimationFrame.bind(dom.window),
    });
    // Browser modules initialize event listeners against this fixture's real DOM.
    ({ ExplorationLeadUI } = await import('./ui.ts'));
    Config._projects = [{ id: 'project', name: 'Survey', permissions: 'ADMIN' }];
    State.resetLayerState();
    State.map = null;
    ExplorationLeadManager.invalidateCache();
});

afterEach(async () => {
    Modal.close('lead-details-modal');
    Modal.close('create-lead-modal');
    ExplorationLeadManager.invalidateCache();
    State.resetLayerState();
    Config._projects = null;
    // This fixture owns its DOM and HTTP server across test setup and teardown.
    dom.window.close();
    for (const [name, descriptor] of globals) {
        if (descriptor) Object.defineProperty(globalThis, name, descriptor);
        else delete (globalThis as Record<string, unknown>)[name];
    }
    const closed = once(server, 'close');
    server.close();
    server.closeAllConnections();
    await closed;
});

it('loads headings and keeps changed directions after a project reload instead of restoring stale cached GeoJSON', async () => {
    await ExplorationLeadManager.loadLeadsForProject('project');
    expect(State.explorationLeads.get('lead')).toMatchObject({ directions: uncheckedDirections([0, 90]) });
    await ExplorationLeadManager.updateLead('lead', { directions: uncheckedDirections([270]) });
    await ExplorationLeadManager.loadLeadsForProject('project');
    expect(State.explorationLeads.get('lead')).toMatchObject({ directions: uncheckedDirections([270]) });
    expect(requests.filter(request => request.method === 'GET')).toHaveLength(2);
});

async function openDetails() {
    await ExplorationLeadManager.loadLeadsForProject('project');
    ExplorationLeadUI.showDetailsModal('lead');
    await vi.waitFor(() => expect(document.getElementById('save-lead-btn')!.onclick).toBeTypeOf('function'));
}

it('does not rewrite imported comments or fractional headings when saving an unchanged detail form', async () => {
    lead.directions = uncheckedDirections([337.5, 359.9]);
    await openDetails();
    expect(directionInput(1).valueAsNumber).toBe(338);
    expect(directionInput(2).valueAsNumber).toBe(0);
    const save = document.getElementById('save-lead-btn')!;
    await save.onclick!(new dom.window.MouseEvent('click') as unknown as PointerEvent);
    expect(requests.filter(request => request.method === 'PATCH')).toEqual([]);
    expect(lead.description).toBe(initialLead().description);
    expect(lead.directions).toEqual(uncheckedDirections([337.5, 359.9]));
});

function directionInput(index: number) {
    const tab = compassButton(`Lead ${index}`);
    expect(tab, `Lead ${index} should select the shared direction editor`).toBeDefined();
    if (tab.getAttribute('aria-selected') !== 'true') tab.click();
    return document.querySelector<HTMLInputElement>(`[aria-label="Direction ${index} in degrees"]`)!;
}

function changeDirection(index: number, value: number) {
    const input = directionInput(index);
    input.value = String(value);
    input.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
}

function compassButton(text: string) {
    return [...document.querySelectorAll<HTMLButtonElement>('#lead-heading-compass button')]
        .find(button => (button.getAttribute('aria-label') ?? button.textContent) === text)!;
}

async function saveDetails() {
    const save = document.getElementById('save-lead-btn')!;
    await save.onclick!(new dom.window.MouseEvent('click') as unknown as PointerEvent);
}

it('saves direction-only edits without resending the source comment and unsets the last removed direction', async () => {
    await openDetails();
    changeDirection(1, 338);
    await saveDetails();
    expect(requests.at(-1)).toEqual({ method: 'PATCH', body: { directions: uncheckedDirections([338, 90]) } });
    expect(lead.description).toBe(initialLead().description);
    await openDetails();
    compassButton('Remove direction').click();
    expect(directionInput(1).valueAsNumber).toBe(90);
    compassButton('Remove direction').click();
    await saveDetails();
    expect(requests.at(-1)).toEqual({ method: 'PATCH', body: { directions: uncheckedDirections([]) } });
    expect(State.explorationLeads.get('lead')!.directions).toEqual(uncheckedDirections([]));
});

it('keeps direction and description drafts visible after the server rejects a save', async () => {
    await openDetails();
    changeDirection(2, 135);
    setChecked(2, true);
    (document.getElementById('lead-description-edit') as HTMLTextAreaElement).value = 'User draft';
    allowWrites = false;
    await saveDetails();
    expect(document.getElementById('lead-details-modal')).not.toBeNull();
    expect(directionInput(2).valueAsNumber).toBe(135);
    expect(isChecked(2)).toBe(true);
    expect((document.getElementById('lead-description-edit') as HTMLTextAreaElement).value).toBe('User draft');
    expect(document.getElementById('save-lead-btn-loading')!.classList.contains('hidden')).toBe(true);
    expect(State.explorationLeads.get('lead')!.directions).toEqual(uncheckedDirections([0, 90]));
});

it('discards cancelled direction edits and renders directions without mutation controls for read-only users', async () => {
    await openDetails();
    changeDirection(1, 180);
    document.querySelector<HTMLButtonElement>('#lead-details-modal [data-close-modal]')!.click();
    expect(State.explorationLeads.get('lead')!.directions).toEqual(uncheckedDirections([0, 90]));
    expect(requests.every(request => request.method === 'GET')).toBe(true);
    Config._projects![0]!.permissions = 'READ_ONLY';
    ExplorationLeadUI.showDetailsModal('lead');
    await vi.waitFor(() => expect(document.querySelector('#lead-heading-compass svg')).not.toBeNull());
    expect(document.querySelector<HTMLInputElement>('#lead-heading-compass input')!.disabled).toBe(true);
    expect(compassButton('Add direction').hidden).toBe(true);
    expect(compassButton('Add direction').disabled).toBe(true);
    expect(document.querySelectorAll('#lead-heading-compass [role="tab"]:not([hidden])')).toHaveLength(2);
    expect(document.getElementById('save-lead-btn')).toBeNull();
});

it('creates a lead with three independently selected directions', async () => {
    ExplorationLeadUI.showCreateModal([6.5, 46.5], 'Survey', 'project');
    await vi.waitFor(() => expect(document.querySelector<HTMLFormElement>('#create-lead-form')!.onsubmit).toBeTypeOf('function'));
    (document.getElementById('lead-description') as HTMLTextAreaElement).value = 'Multiple passages';
    compassButton('Set direction').click();
    compassButton('Add direction').click();
    compassButton('Add direction').click();
    const editor = directionInput(1);
    changeDirection(1, 23);
    changeDirection(2, 123);
    changeDirection(3, 300);
    expect(directionInput(1)).toBe(editor);
    expect(editor.valueAsNumber).toBe(23);
    expect(compassButton('Add direction').disabled).toBe(true);
    const form = document.getElementById('create-lead-form') as HTMLFormElement;
    await form.onsubmit!(new dom.window.Event('submit') as unknown as SubmitEvent);
    expect(requests.at(-1)).toEqual({ method: 'POST', body: {
        latitude: '46.5000000', longitude: '6.5000000',
        description: 'Multiple passages', directions: uncheckedDirections([23, 123, 300]),
    } });
    expect(State.explorationLeads.get('lead')).toMatchObject({ directions: uncheckedDirections([23, 123, 300]), lineName: 'Survey' });
});

it.each([22.5, 399])('keeps invalid direction %s open instead of silently saving its previous value', async (value) => {
    await openDetails();
    changeDirection(1, value);
    compassButton('Mark checked').click();
    compassButton('Check all').click();
    expect(isChecked(1)).toBe(false);
    expect(isChecked(2)).toBe(false);
    await saveDetails();
    expect(document.getElementById('lead-details-modal')).not.toBeNull();
    expect(directionInput(1).valueAsNumber).toBe(value);
    expect(requests.every(request => request.method === 'GET')).toBe(true);
});

function isChecked(index: number) {
    return compassButton(`Lead ${index}`).getAttribute('aria-description') === 'Checked';
}

function setChecked(index: number, value: boolean) {
    directionInput(index);
    if (isChecked(index) !== value) compassButton(value ? 'Mark checked' : 'Mark unchecked').click();
    expect(isChecked(index)).toBe(value);
}

it('scopes completion actions to the selected lead and permits both bulk operations on a mixed draft', async () => {
    await openDetails();
    expect(isChecked(1)).toBe(false);
    setChecked(1, true);
    directionInput(2);
    expect(isChecked(1)).toBe(true);
    expect(isChecked(2)).toBe(false);
    expect(compassButton('Check all').disabled).toBe(false);
    expect(compassButton('Uncheck all').disabled).toBe(false);
    compassButton('Check all').click();
    expect(isChecked(1)).toBe(true);
    expect(isChecked(2)).toBe(true);
    expect(compassButton('Check all').disabled).toBe(true);
    setChecked(2, false);
    compassButton('Uncheck all').click();
    expect(isChecked(1)).toBe(false);
    expect(isChecked(2)).toBe(false);
    expect(compassButton('Uncheck all').disabled).toBe(true);
    setChecked(1, true);
    expect(requests.every(request => request.method === 'GET')).toBe(true);
    await saveDetails();
    expect(lead.directions).toEqual([{ heading: 0, checked: true }, { heading: 90, checked: false }]);
});

it('saves checked status with its heading, preserving the comment and checked state on later heading edits', async () => {
    await openDetails();
    setChecked(1, true);
    expect(State.explorationLeads.get('lead')!.directions[0]!.checked).toBe(false);
    await saveDetails();
    expect(requests.at(-1)).toEqual({ method: 'PATCH', body: { directions: [
        { heading: 0, checked: true }, { heading: 90, checked: false },
    ] } });
    expect(lead.description).toBe(initialLead().description);
    await openDetails();
    changeDirection(1, 180);
    await saveDetails();
    expect(lead.directions[0]).toEqual({ heading: 180, checked: true });
    await ExplorationLeadManager.loadLeadsForProject('project');
    expect(State.explorationLeads.get('lead')!.directions).toEqual(lead.directions);
});

it('applies bulk status edits as a draft and preserves checked states after removing another entry', async () => {
    await openDetails();
    compassButton('Check all').click();
    document.querySelector<HTMLButtonElement>('#lead-details-modal [data-close-modal]')!.click();
    expect(requests.every(request => request.method === 'GET')).toBe(true);
    expect(State.explorationLeads.get('lead')!.directions.every(direction => !direction.checked)).toBe(true);
    await openDetails();
    compassButton('Check all').click();
    compassButton('Remove direction').click();
    await saveDetails();
    expect(lead.directions).toEqual([{ heading: 90, checked: true }]);
    await openDetails();
    compassButton('Remove direction').click();
    await saveDetails();
    expect(lead.directions).toEqual([{ heading: null, checked: true }]);
});

it('reopens all entries and makes newly added directions unchecked without resetting existing checked status', async () => {
    lead.directions = [{ heading: null, checked: true }];
    await openDetails();
    compassButton('Set direction').click();
    compassButton('Add direction').click();
    await saveDetails();
    expect(lead.directions).toEqual([{ heading: 0, checked: true }, { heading: 90, checked: false }]);
    await openDetails();
    compassButton('Check all').click();
    await saveDetails();
    await openDetails();
    compassButton('Uncheck all').click();
    await saveDetails();
    expect(lead.directions).toEqual(uncheckedDirections([0, 90]));
});

it('sets an undirected checked entry at the three-lead limit and preserves duplicate headings when removing it', async () => {
    lead.directions = [{ heading: 90, checked: false }, { heading: null, checked: true }, { heading: 90, checked: true }];
    await openDetails();
    directionInput(2);
    compassButton('Set direction').click();
    await saveDetails();
    expect(lead.directions).toEqual([{ heading: 90, checked: false }, { heading: 0, checked: true }, { heading: 90, checked: true }]);
    await openDetails();
    directionInput(2);
    compassButton('Remove direction').click();
    await saveDetails();
    expect(lead.directions).toEqual([{ heading: 90, checked: false }, { heading: 90, checked: true }]);
});

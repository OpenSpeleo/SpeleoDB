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

function initialLead() {
    return {
        id: 'lead', project: 'project', latitude: '46.5', longitude: '6.5',
        description: '  Original !N!\nFull comment  ', headings: [0, 90],
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
    expect(State.explorationLeads.get('lead')).toMatchObject({ headings: [0, 90] });
    await ExplorationLeadManager.updateLead('lead', { headings: [270] });
    await ExplorationLeadManager.loadLeadsForProject('project');
    expect(State.explorationLeads.get('lead')).toMatchObject({ headings: [270] });
    expect(requests.filter(request => request.method === 'GET')).toHaveLength(2);
});

async function openDetails() {
    await ExplorationLeadManager.loadLeadsForProject('project');
    ExplorationLeadUI.showDetailsModal('lead');
    await vi.waitFor(() => expect(document.getElementById('save-lead-btn')!.onclick).toBeTypeOf('function'));
}

it('does not rewrite imported comments or fractional headings when saving an unchanged detail form', async () => {
    lead.headings = [337.5, 359.9];
    await openDetails();
    expect(directionInput(1).valueAsNumber).toBe(338);
    expect(directionInput(2).valueAsNumber).toBe(0);
    const save = document.getElementById('save-lead-btn')!;
    await save.onclick!(new dom.window.MouseEvent('click') as unknown as PointerEvent);
    expect(requests.filter(request => request.method === 'PATCH')).toEqual([]);
    expect(lead.description).toBe(initialLead().description);
    expect(lead.headings).toEqual([337.5, 359.9]);
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
    expect(requests.at(-1)).toEqual({ method: 'PATCH', body: { headings: [338, 90] } });
    expect(lead.description).toBe(initialLead().description);
    await openDetails();
    compassButton('Remove direction').click();
    expect(directionInput(1).valueAsNumber).toBe(90);
    compassButton('Remove direction').click();
    await saveDetails();
    expect(requests.at(-1)).toEqual({ method: 'PATCH', body: { headings: [] } });
    expect(State.explorationLeads.get('lead')!.headings).toEqual([]);
});

it('keeps direction and description drafts visible after the server rejects a save', async () => {
    await openDetails();
    changeDirection(2, 135);
    (document.getElementById('lead-description-edit') as HTMLTextAreaElement).value = 'User draft';
    allowWrites = false;
    await saveDetails();
    expect(document.getElementById('lead-details-modal')).not.toBeNull();
    expect(directionInput(2).valueAsNumber).toBe(135);
    expect((document.getElementById('lead-description-edit') as HTMLTextAreaElement).value).toBe('User draft');
    expect(document.getElementById('save-lead-btn-loading')!.classList.contains('hidden')).toBe(true);
    expect(State.explorationLeads.get('lead')!.headings).toEqual([0, 90]);
});

it('discards cancelled direction edits and renders directions without mutation controls for read-only users', async () => {
    await openDetails();
    changeDirection(1, 180);
    document.querySelector<HTMLButtonElement>('#lead-details-modal [data-close-modal]')!.click();
    expect(State.explorationLeads.get('lead')!.headings).toEqual([0, 90]);
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
    compassButton('Add direction').click();
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
        description: 'Multiple passages', headings: [23, 123, 300],
    } });
    expect(State.explorationLeads.get('lead')).toMatchObject({ headings: [23, 123, 300], lineName: 'Survey' });
});

it.each([22.5, 399])('keeps invalid direction %s open instead of silently saving its previous value', async (value) => {
    await openDetails();
    changeDirection(1, value);
    await saveDetails();
    expect(document.getElementById('lead-details-modal')).not.toBeNull();
    expect(directionInput(1).valueAsNumber).toBe(value);
    expect(requests.every(request => request.method === 'GET')).toBe(true);
});

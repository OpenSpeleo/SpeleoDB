import type { LandmarkDetailsContext } from '../../ts-types/controllers/landmark-details.ts';
import { init as initialize } from './landmark-details.ts';
import { loadJQuery } from '../test/api-server.ts';

function init(context?: unknown) { return initialize(context as LandmarkDetailsContext); }

beforeAll(loadJQuery);
beforeEach(() => {
    document.body.innerHTML = '<div id="landmark-root"><script id="landmark_collection_context" type="application/json">{"id":"collection","name":"Cave","color":"#123456","is_personal":false}</script><button class="landmark-locate-btn">Locate</button></div>';
});
afterEach(() => {
    delete window.LANDMARK_DETAILS_CONTEXT;
    document.body.innerHTML = '';
});

it('publishes context synchronously and initializes the real collection controls', async () => {
    const context = { canWrite: false, collectionId: 'collection' };
    const pending = init(context);
    expect(window.LANDMARK_DETAILS_CONTEXT).toBe(context);
    await expect(pending).resolves.toBeUndefined();
    const event = new MouseEvent('click', { bubbles: true, cancelable: true });
    let reachedParent = false;
    document.getElementById('landmark-root')!.addEventListener('click', () => { reachedParent = true; }, { once: true });
    document.querySelector<HTMLButtonElement>('.landmark-locate-btn')!.dispatchEvent(event);
    expect(reachedParent).toBe(false);
});

it('overwrites context and permits repeated initialization without optional controls', async () => {
    await init({ canWrite: false });
    document.body.replaceChildren();
    await expect(init()).resolves.toBeUndefined();
    expect(window.LANDMARK_DETAILS_CONTEXT).toBeUndefined();
});

it('propagates an unavailable table vendor while retaining the published context', async () => {
    // A page with a table requires its DataTables vendor; no substitute is installed.
    document.body.insertAdjacentHTML('beforeend', '<table id="collection_landmarks_table"></table>');
    const context = { canWrite: false };
    await expect(init(context)).rejects.toThrow(TypeError);
    expect(window.LANDMARK_DETAILS_CONTEXT).toBe(context);
});

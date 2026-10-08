import type { DOMWindow } from 'jsdom';
import type { GISUploadListContext } from '../ts-types/controllers/gis-lists.ts';
import type { UploadOptions, UploadError } from '../ts-types/domain/upload.ts';
interface UploadRecord { id: string; name: string }
interface UploadResult { response?: UploadRecord | null; error?: UploadError }
interface UploadConfiguration { url: string; unavailableUrl: string; sessionCookie: { name: string; value: string } }
// Invoked by pytest with an authenticated Django live_server configuration on
// stdin. JSDOM's unmodified XMLHttpRequest sends real HTTP and multipart bodies.
import './jsdom-runtime.ts';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';

// Defer JSDOM until its installed HTTP dependency has been selected.
const { CookieJar, JSDOM, VirtualConsole } = await import('jsdom');

const configuration = JSON.parse(readFileSync(0, 'utf8')) as UploadConfiguration;
const cookieJar = new CookieJar();
cookieJar.setCookieSync(
    `${configuration.sessionCookie.name}=${configuration.sessionCookie.value}; Path=/`,
    configuration.url,
);
const virtualConsole = new VirtualConsole();
virtualConsole.forwardTo(console);
const dom = await JSDOM.fromURL(configuration.url, {
    cookieJar,
    runScripts: 'outside-only',
    virtualConsole,
});
const { window } = dom;
Object.assign(globalThis, {
    window,
    document: window.document,
    XMLHttpRequest: window.XMLHttpRequest,
    FormData: window.FormData,
    File: window.File,
});
window.eval(await readFile(new URL('../frontend_public/static/ts/vendors/jquery-3.7.1.js', import.meta.url), 'utf8'));
(globalThis as unknown as {$: JQueryStatic}).$ = (window as DOMWindow & {jQuery: JQueryStatic}).jQuery;
const { init } = await import('../frontend_common/controllers/gis-layers.ts');
const { createProgressBarHTML, UploadProgressController, uploadWithProgress } = await import(
    '../frontend_private/static/private/ts/map_viewer/components/upload.ts'
);
const contextElement = document.querySelector('[data-speleodb-controller="gis-layers"]');
assert.ok(contextElement, 'The authenticated Django GIS-layer page must load');
const context = JSON.parse(contextElement.textContent) as GISUploadListContext;
const checks: string[] = [];
const stored: {id: string; name: string; contents: string}[] = [];
const source = '{ "type": "FeatureCollection", "features": [], "note": "Original whitespace and bytes stay intact." }';

function element<T extends HTMLElement = HTMLElement>(id: string): T {
    const found = document.getElementById(id);
    assert.ok(found, `Missing real page element: ${id}`);
    return found as T;
}

function waitFor(predicate: () => boolean, description: string) {
    return new Promise<void>((resolve, reject) => {
        const started = Date.now();
        const check = () => {
            if (predicate()) return resolve();
            if (Date.now() - started >= 15000) return reject(new Error(`Timed out: ${description}`));
            window.setTimeout(check, 10);
        };
        check();
    });
}

function chooseFile(contents: string, filename: string) {
    const file = new window.File([contents], filename, { type: 'application/geo+json' });
    const event = new window.Event('drop', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'dataTransfer', { value: { files: [file] } });
    element('upload-layer-drop-zone').dispatchEvent(event);
}

function submit() {
    element('upload-layer-form').dispatchEvent(new window.Event('submit', {
        bubbles: true, cancelable: true,
    }));
}

function form(name: string, contents = source, filename = `${name}.geojson`) {
    const data = new window.FormData();
    data.append('name', name);
    data.append('color', '#377eb8');
    data.append('source_file', new window.File([contents], filename));
    return data;
}

function request(url: string, data: FormData, options: UploadOptions<UploadRecord> = {}) {
    const progress: [number, number, number][] = [];
    const phases: string[] = [];
    let xhr!: XMLHttpRequest;
    const done = new Promise<UploadResult>(resolve => {
        xhr = uploadWithProgress(url, data, {
            ...options,
            onProgress: (...values) => progress.push(values),
            onUploaded: () => phases.push('uploaded'),
            onSuccess: response => resolve({ response: response as UploadRecord | null }),
            onError: error => resolve({ error }),
        });
    });
    return { xhr, done, progress, phases };
}

try {
    const listRequests: {method: string | undefined; status: number; data: UploadRecord[]}[] = [];
    $(document).on('ajaxComplete', (_event: JQuery.Event, xhr: JQuery.jqXHR<UploadRecord[]>, options: JQuery.AjaxSettings) => {
        if (options.url === context.listEndpoint) {
            listRequests.push({ method: options.type, status: xhr.status, data: xhr.responseJSON as UploadRecord[] });
        }
    });
    init(context);
    await waitFor(() => listRequests.length === 1, 'initial real list response');
    assert.equal(listRequests[0]!.status, 200);
    assert.ok(Array.isArray(listRequests[0]!.data));
    assert.equal(listRequests[0]!.data.length, 0);

    element('upload-layer-open').click();
    element('upload-layer-modal').click();
    assert.equal(element('upload-layer-modal').classList.contains('hidden'), false);
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }));
    assert.equal(element('upload-layer-modal').classList.contains('hidden'), true);
    element('upload-layer-open').click();
    chooseFile('invalid extension', 'layer.exe');
    assert.equal(element<HTMLButtonElement>('upload-layer-button').disabled, true);
    assert.match(element('upload-layer-error-text').textContent, /Choose KML/);
    checks.push('gis-modal');

    chooseFile(source, 'browser-controller.geojson');
    const observedLabels: (string | null)[] = [];
    const labels = new window.MutationObserver(records => {
        for (const record of records) {
            for (const node of record.addedNodes) observedLabels.push(node.textContent);
        }
    });
    labels.observe(element('upload-layer-progress-label'), { childList: true });
    labels.observe(element('upload-layer-button-text'), { childList: true });
    submit();
    assert.equal(element('upload-layer-progress-label').textContent, 'Uploading…');
    const dismissButtons = [...document.querySelectorAll<HTMLButtonElement>('[data-layer-upload-action="hide"]')];
    assert.ok(dismissButtons.every(button => button.disabled));
    dismissButtons[0]!.click();
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }));
    assert.equal(element('upload-layer-modal').classList.contains('hidden'), false);
    await waitFor(() => listRequests.length === 2, 'exactly one real list refresh after upload');
    labels.disconnect();
    assert.equal(listRequests[1]!.status, 200);
    assert.equal(listRequests[1]!.data.length, 1);
    assert.equal(element('upload-layer-modal').classList.contains('hidden'), true);
    assert.equal(element('modal_success_txt').textContent, 'GIS Layer uploaded successfully!');
    assert.match(element('gis-layers-table-body').textContent, /browser-controller/);
    assert.ok(observedLabels.includes('Saving layer…'), observedLabels as unknown as string);
    assert.ok(observedLabels.includes('Saving…'), observedLabels as unknown as string);
    assert.equal(observedLabels.includes('Preparing map data…'), false);
    stored.push({ id: listRequests[1]!.data[0]!.id, name: 'browser-controller', contents: source });
    checks.push('gis-upload-and-refresh');

    element('upload-layer-open').click();
    chooseFile('{"type":"not-a-topology"}', 'broken.topojson');
    submit();
    await waitFor(() => !element('upload-layer-error-message').classList.contains('hidden'), 'real TopoJSON processor rejection');
    assert.equal(element('upload-layer-error-text').textContent, 'The uploaded file is not a TopoJSON topology.');
    assert.equal(element('upload-layer-modal').classList.contains('hidden'), false);
    assert.ok(dismissButtons.every(button => !button.disabled));
    assert.equal(listRequests.length, 2);
    checks.push('gis-server-validation');

    const successful = request(context.listEndpoint, form('browser-helper'));
    assert.ok(successful.xhr instanceof window.XMLHttpRequest);
    const { response, error } = await successful.done;
    assert.equal(error, undefined);
    assert.equal(successful.xhr.status, 201);
    assert.equal(response!.name, 'browser-helper');
    assert.ok(successful.progress.length > 0);
    for (const [percent, loaded, total] of successful.progress) {
        assert.ok(total > 0);
        assert.equal(percent, Math.round(100 * loaded / total));
    }
    assert.equal(successful.progress.at(-1)![0], 100);
    assert.deepEqual(successful.phases, ['uploaded']);
    stored.push({ id: response!.id, name: 'browser-helper-renamed', contents: source });
    checks.push('upload-helper-success-and-progress');

    const update = new window.FormData();
    update.append('name', 'browser-helper-renamed');
    const edited = request(`${context.listEndpoint}${response!.id}/`, update, { method: 'PATCH' });
    const editedResult = await edited.done;
    assert.equal(edited.xhr.status, 200);
    assert.equal(editedResult.response!.name, 'browser-helper-renamed');
    checks.push('upload-helper-custom-method');

    // The preceding writes prove a real session and CSRF token are accepted.
    // Removing both token sources makes the actual Django request fail CSRF.
    const csrfInput = document.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]')!;
    const csrfValue = csrfInput.value;
    const csrfCookie = document.cookie.split('; ').find(cookie => cookie.startsWith('csrftoken='));
    csrfInput.value = '';
    document.cookie = 'csrftoken=; Max-Age=0; Path=/';
    const rejectedCSRF = request(context.listEndpoint, form('must-not-save-csrf'));
    assert.match((await rejectedCSRF.done).error!.message, /CSRF/);
    assert.equal(rejectedCSRF.xhr.status, 403);
    csrfInput.value = csrfValue;
    document.cookie = `${csrfCookie}; Path=/`;
    checks.push('upload-helper-csrf');

    const empty = request(context.listEndpoint, new window.FormData(), { method: 'HEAD' });
    assert.equal((await empty.done).response, null);
    assert.equal(empty.xhr.status, 200);
    assert.equal(empty.xhr.responseText, '');
    checks.push('upload-helper-empty-response');

    const html = request(configuration.url, new window.FormData(), { method: 'GET' });
    const htmlError = (await html.done).error!;
    assert.match(htmlError.message, /unreadable response/);
    assert.equal(htmlError.ambiguous, true);
    assert.equal(htmlError.status, 200);
    assert.equal(html.xhr.status, 200);
    checks.push('upload-helper-html-response');

    const invalid = request(context.listEndpoint, form('broken', '{}', 'broken.topojson'));
    const invalidError = (await invalid.done).error!;
    assert.equal(invalidError.message, 'The uploaded file is not a TopoJSON topology.');
    assert.equal(invalidError.status, 422);
    assert.equal(invalidError.ambiguous, false);
    assert.equal(invalid.xhr.status, 422);
    const invalidName = request(context.listEndpoint, form('x'.repeat(256)));
    const nameError = (await invalidName.done).error!;
    assert.equal(invalidName.xhr.status, 400);
    assert.match(nameError.message, /name:.*255/);
    assert.ok(Array.isArray((nameError.payload as {errors: {name: unknown}}).errors.name));
    checks.push('upload-helper-server-error');

    const unavailable = request(configuration.unavailableUrl, new window.FormData());
    const networkError = (await unavailable.done).error!;
    assert.equal(networkError.message, 'Network error during upload');
    assert.equal(networkError.status, 0);
    assert.equal(networkError.ambiguous, true);
    assert.equal(unavailable.xhr.status, 0);
    checks.push('upload-helper-network-error');

    document.body.insertAdjacentHTML('beforeend', createProgressBarHTML('browser-progress'));
    const controller = new UploadProgressController('browser-progress');
    const uploaded = controller.upload(context.listEndpoint, form('browser-progress'));
    assert.equal(element('browser-progress-container').classList.contains('hidden'), false);
    const uploadedResult = await uploaded as UploadRecord;
    assert.equal(uploadedResult.name, 'browser-progress');
    assert.match(element('browser-progress-status').textContent, /Upload complete!/);
    stored.push({ id: uploadedResult.id, name: 'browser-progress', contents: source });
    checks.push('upload-controller-success');

    await assert.rejects(controller.upload(context.listEndpoint, form('broken', '{}', 'broken.topojson')), /not a TopoJSON topology/);
    assert.ok(element('browser-progress-bar').classList.contains('bg-red-500'));
    checks.push('upload-controller-rejection');

    const cancellation = new UploadProgressController('browser-progress');
    const cancelled = cancellation.upload(context.listEndpoint, form('must-not-save-cancelled'));
    const nativeRequest = cancellation.xhr!;
    let abortCount = 0;
    nativeRequest.addEventListener('abort', () => { abortCount += 1; });
    cancellation.cancel();
    cancellation.cancel();
    await assert.rejects(cancelled, /Upload cancelled/);
    assert.equal(abortCount, 1);
    assert.equal(cancellation.xhr, null);
    assert.equal(nativeRequest.readyState, window.XMLHttpRequest.UNSENT);
    assert.equal(element('browser-progress-container').classList.contains('hidden'), true);
    checks.push('upload-controller-cancellation');
    assert.equal(listRequests.length, 2, 'Only the successful GIS controller upload reloads its list');

    process.stdout.write(JSON.stringify({ checks, stored }));
} finally {
    window.close();
}

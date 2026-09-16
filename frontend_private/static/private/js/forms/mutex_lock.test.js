// @vitest-environment node

import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { JSDOM, VirtualConsole } from 'jsdom';
import { attachMutexLock } from './mutex_lock.js';

const JQUERY_SOURCE = readFileSync(new URL(
    '../../../../../frontend_public/static/js/vendors/jquery-3.7.1.js', import.meta.url,
), 'utf8');

describe('project mutex actions over HTTP', () => {
    let server;
    let dom;
    let events;
    let browserErrors;
    let requests;
    let originalGlobals;

    beforeEach(async () => {
        events = [];
        browserErrors = [];
        requests = [];
        server = createServer((request) => requests.push(request));
        server.listen(0, '127.0.0.1');
        await once(server, 'listening');

        const virtualConsole = new VirtualConsole();
        virtualConsole.on('jsdomError', error => {
            // JSDOM reports real reload calls here because navigation is unsupported.
            if (error.type === 'not-implemented' && /navigation/.test(error.message)) {
                events.push('reload');
            } else {
                browserErrors.push(error);
            }
        });
        dom = new JSDOM(`
            <input type="hidden" name="csrfmiddlewaretoken" value="mutex-csrf-token">
            <button type="button" id="btn_lock_project">Enable Project Edition</button>
            <button type="button" class="btn_unlock">Unlock</button>
            <div id="error_div"></div><div id="success_div"></div>
            <div id="modal_success" style="display:none"><span id="modal_success_txt"></span></div>
            <div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div>
            <div id="modal_confirmation" style="display:none"></div>
        `, {
            url: `http://127.0.0.1:${server.address().port}/private/project/test/upload/`,
            runScripts: 'outside-only',
            virtualConsole,
        });
        dom.window.eval(JQUERY_SOURCE);
        originalGlobals = new Map(['window', 'document', '$'].map(name => [
            name, Object.getOwnPropertyDescriptor(globalThis, name),
        ]));
        Object.assign(globalThis, {
            window: dom.window,
            document: dom.window.document,
            $: dom.window.jQuery,
        });
        $(document).on('ajaxComplete', () => events.push('complete'));
    });

    afterEach(async () => {
        dom.window.close();
        for (const [name, descriptor] of originalGlobals) {
            if (descriptor) Object.defineProperty(globalThis, name, descriptor);
            else delete globalThis[name];
        }
        const closed = once(server, 'close');
        server.close();
        server.closeAllConnections();
        await closed;
        expect(browserErrors).toEqual([]);
    });

    function ajaxComplete() {
        return new Promise(resolve => $(document).one('ajaxComplete', resolve));
    }

    function respond(response, status, body) {
        response.writeHead(status, { 'Content-Type': 'application/json' });
        response.end(JSON.stringify(body));
    }

    it('acquires with CSRF and reloads immediately, suppressing duplicate clicks while pending', async () => {
        attachMutexLock({ lockUrl: '/acquire/', reloadDelayMs: 2000 });
        const button = document.getElementById('btn_lock_project');
        const received = once(server, 'request');
        const completed = ajaxComplete();

        button.click();
        const [request, response] = await received;
        expect(request.method).toBe('POST');
        expect(request.url).toBe('/acquire/');
        expect(request.headers['x-csrftoken']).toBe('mutex-csrf-token');
        expect(button.disabled).toBe(true);
        expect(events).toEqual([]);
        button.click();
        // A programmatic jQuery event must also respect the pending-action guard.
        $(button).triggerHandler('click');

        respond(response, 200, { success: true });
        await completed;
        expect(events).toEqual(['reload', 'complete']);
        expect(requests).toHaveLength(1);
        expect(button.disabled).toBe(true);
        expect(document.getElementById('modal_success').style.display).toBe('none');
    });

    it('shows escaped API errors and allows retry without navigating away', async () => {
        attachMutexLock({ lockUrl: '/acquire/' });
        const button = document.getElementById('btn_lock_project');
        let received = once(server, 'request');
        let completed = ajaxComplete();
        button.click();
        const [, failureResponse] = await received;
        const message = '<img src=x onerror="alert(1)"> already owns this lock';
        respond(failureResponse, 409, { detail: message });
        await completed;

        expect(events).toEqual(['complete']);
        expect(button.disabled).toBe(false);
        expect(document.getElementById('modal_error').style.display).toBe('flex');
        expect(document.getElementById('modal_error_txt').textContent).toBe(message);
        expect(document.querySelector('#modal_error_txt img')).toBeNull();

        received = once(server, 'request');
        completed = ajaxComplete();
        button.click();
        const [retryRequest, retryResponse] = await received;
        expect(retryRequest.url).toBe('/acquire/');
        expect(button.disabled).toBe(true);
        respond(retryResponse, 200, { success: true });
        await completed;
        expect(events).toEqual(['complete', 'reload', 'complete']);
        expect(requests).toHaveLength(2);
    });

    it('keeps the existing unlock success modal and deferred reload', async () => {
        attachMutexLock({ unlockUrl: '/release/', reloadDelayMs: 1 });
        const received = once(server, 'request');
        const completed = ajaxComplete();
        document.querySelector('.btn_unlock').click();
        const [request, response] = await received;
        expect(request.method).toBe('POST');
        expect(request.url).toBe('/release/');
        expect(request.headers['x-csrftoken']).toBe('mutex-csrf-token');
        const reloaded = new Promise(resolve => dom.virtualConsole.on('jsdomError', resolve));
        respond(response, 200, { success: true });
        await completed;
        expect(events).toEqual(['complete']);
        expect(document.getElementById('modal_success').style.display).toBe('flex');
        expect(document.getElementById('modal_success_txt').textContent)
            .toBe('The project has been unlocked for edition.');
        await reloaded;
        expect(events).toEqual(['complete', 'reload']);
    });
});

// @vitest-environment node

import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import type { IncomingMessage, Server, ServerResponse } from 'node:http';
import type { AddressInfo } from 'node:net';
import { JSDOM, VirtualConsole } from 'jsdom';
import { attachDangerZone } from './danger_zone.ts';
import { attachEntityCrudForm } from './entity_crud_form.ts';

const JQUERY_SOURCE = readFileSync(new URL(
    '../../../../../frontend_public/static/ts/vendors/jquery-3.7.1.js', import.meta.url,
), 'utf8');

describe('shared form mutations over HTTP', () => {
    let server: Server;
    let dom: JSDOM;
    let requests: IncomingMessage[];
    let originalGlobals: Map<string, PropertyDescriptor | undefined>;
    let browserErrors: Error[];

    beforeEach(async () => {
        requests = [];
        browserErrors = [];
        server = createServer(request => requests.push(request));
        server.listen(0, '127.0.0.1');
        await once(server, 'listening');
        const virtualConsole = new VirtualConsole();
        virtualConsole.on('jsdomError', error => browserErrors.push(error));
        dom = new JSDOM(`
            <form id="details_form">
                <input type="hidden" name="csrfmiddlewaretoken" value="form-csrf-token">
                <input name="name" value="Updated name">
                <button type="submit" id="btn_submit">Save</button>
            </form>
            <button id="btn_delete">Delete</button>
            <div id="error_div"></div><div id="success_div"></div>
            <div id="modal_confirmation" style="display:none"><button id="btn_confirmed_delete">Confirm</button></div>
            <div id="modal_success" style="display:none"><span id="modal_success_txt"></span></div>
            <div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div>
        `, {
            url: `http://127.0.0.1:${(server.address() as AddressInfo).port}/details/`,
            runScripts: 'outside-only', virtualConsole,
        });
        dom.window.eval(JQUERY_SOURCE);
        originalGlobals = new Map(['window', 'document', '$', 'FormData'].map(name => [
            name, Object.getOwnPropertyDescriptor(globalThis, name),
        ]));
        Object.assign(globalThis, {
            window: dom.window, document: dom.window.document, FormData: dom.window.FormData,
            $: (dom.window as typeof dom.window & { jQuery: JQueryStatic }).jQuery,
        });
    });

    afterEach(async () => {
        dom.window.close();
        for (const [name, descriptor] of originalGlobals) {
            if (descriptor) Object.defineProperty(globalThis, name, descriptor);
            else delete (globalThis as Record<string, unknown>)[name];
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

    function respond(response: ServerResponse) {
        response.writeHead(200, { 'Content-Type': 'application/json' });
        response.end('{}');
    }

    it('forwards PATCH, serialized fields, and the CSRF header to the configured endpoint', async () => {
        attachEntityCrudForm({ formId: 'details_form', endpoint: '/entity/', method: 'PATCH' });
        const received = once(server, 'request') as Promise<[IncomingMessage, ServerResponse]>;
        const completed = ajaxComplete();
        document.getElementById('btn_submit')!.click();
        const [request, response] = await received;
        const chunks: Buffer[] = [];
        for await (const chunk of request) chunks.push(Buffer.from(chunk as Uint8Array));
        expect(request.method).toBe('PATCH');
        expect(request.url).toBe('/entity/');
        expect(request.headers['x-csrftoken']).toBe('form-csrf-token');
        expect(request.headers['content-type']).toContain('application/json');
        expect(JSON.parse(Buffer.concat(chunks).toString())).toEqual({
            csrfmiddlewaretoken: 'form-csrf-token', name: 'Updated name',
        });
        respond(response);
        await completed;
        expect(requests).toHaveLength(1);
    });

    it('starts no request before confirmation and sends exactly one DELETE with CSRF afterward', async () => {
        attachDangerZone({ deleteUrl: '/entity/' });
        let starts = 0;
        $(document).on('ajaxSend', () => { starts += 1; });
        document.getElementById('btn_delete')!.click();
        expect(starts).toBe(0);
        expect(requests).toHaveLength(0);
        const received = once(server, 'request') as Promise<[IncomingMessage, ServerResponse]>;
        const completed = ajaxComplete();
        document.getElementById('btn_confirmed_delete')!.click();
        const [request, response] = await received;
        expect(request.method).toBe('DELETE');
        expect(request.url).toBe('/entity/');
        expect(request.headers['x-csrftoken']).toBe('form-csrf-token');
        respond(response);
        await completed;
        expect(starts).toBe(1);
        expect(requests).toHaveLength(1);
    });
});

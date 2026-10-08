import type { IncomingHttpHeaders, Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import type { JSDOM } from 'jsdom';
import type { ProjectUploadContext } from '../../ts-types/controllers/project-upload.ts';
interface UploadRequest {method: string | undefined; url: string | undefined; headers: IncomingHttpHeaders; body: string}
interface UploadAjaxCallback { success(data: {browser_url: string; geojson_status?: string | undefined}, status: string, xhr: {status: number}): void }
const jsdomHost = globalThis as typeof globalThis & {jsdom: JSDOM};
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { resolve } from 'node:path';

import { init as initialize } from './project-upload.ts';

function init(context?: unknown) { return initialize(context as ProjectUploadContext); }
const root = process.cwd();
const jquery = readFileSync(resolve(root, 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const template = readFileSync(resolve(root, 'frontend_private/templates/pages/project/upload.html'), 'utf8');
const errorModal = readFileSync(resolve(root, 'frontend_private/templates/snippets/modal_error.html'), 'utf8');

let server: Server;
let originalUrl: string;
let requests: UploadRequest[];
let responseStatus: number;

beforeAll(() => {
    (0, eval)(jquery);
});

beforeEach(async () => {
    requests = [];
    responseStatus = 304;
    server = createServer((request, response) => {
        response.setHeader('Access-Control-Allow-Origin', '*');
        if (request.method === 'OPTIONS') {
            response.setHeader('Access-Control-Allow-Methods', 'PUT');
            response.setHeader('Access-Control-Allow-Headers', 'X-CSRFToken, X-Requested-With');
            response.writeHead(204);
            response.end();
            return;
        }
        const chunks: Buffer[] = [];
        request.on('data', (chunk: Buffer) => chunks.push(chunk));
        request.on('end', () => {
            requests.push({ method: request.method, url: request.url, headers: request.headers, body: Buffer.concat(chunks).toString() });
            response.writeHead(responseStatus, { 'Content-Type': 'application/json' });
            response.end(JSON.stringify({ detail: 'Project is locked by another user.' }));
        });
    });
    await new Promise<void>((resolve, reject) => {
        server.once('error', reject);
        server.listen(0, '127.0.0.1', resolve);
    });
    originalUrl = window.location.href;
    jsdomHost.jsdom.reconfigure({ url: `http://127.0.0.1:${(server.address() as AddressInfo).port}/upload/` });
    document.body.innerHTML = template
        .replace('{% csrf_token %}', '<input type="hidden" name="csrfmiddlewaretoken" value="upload-csrf">')
        .replace(/{%.*?%}/gs, '') + errorModal;
    const initialization = init({ endpoint: '/api/upload/', maxFiles: 10, maxFileSizeMb: 2, maxTotalSizeMb: 50 });
    window.dispatchEvent(new Event('load'));
    await initialization;
});

afterEach(async () => {
    $(document.body).off();
    document.body.innerHTML = '';
    jsdomHost.jsdom.reconfigure({ url: originalUrl });
    server.closeAllConnections();
    await new Promise<Error | undefined>(resolve => server.close(resolve));
});

function selectFile() {
    const input = (document.getElementById('artifact') as HTMLInputElement);
    Object.defineProperty(input, 'files', {
        configurable: true,
        value: [new File(['survey contents'], 'survey.dat')],
    });
    input.dispatchEvent(new Event('change', { bubbles: true }));
}

it.each(['form submission', 'Upload Revision button'])('uploads the title and selected files through %s without resetting', async action => {
    const form = (document.getElementById('file_upload_form') as HTMLFormElement);
    const button = (document.getElementById('btn_submit') as HTMLButtonElement);
    expect(button.type).toBe('submit');
    expect(button.form).toBe(form);
    $('#message').val('Updated survey');
    selectFile();
    const submissions: Event[] = [];
    const resets: Event[] = [];
    form.addEventListener('submit', event => submissions.push(event));
    form.addEventListener('reset', event => resets.push(event));

    // JSDOM does not synthesize Enter's browser default action. requestSubmit
    // exercises the same native submit event without relying on a button click.
    if (action === 'form submission') form.requestSubmit();
    else button.click();

    expect(submissions).toHaveLength(1);
    expect(submissions[0]!.defaultPrevented).toBe(true);
    expect(resets).toHaveLength(0);
    await vi.waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0]).toMatchObject({ method: 'PUT', url: '/api/upload/' });
    expect(requests[0]!.headers['x-csrftoken']).toBe('upload-csrf');
    expect(requests[0]!.headers['content-type']).toContain('multipart/form-data; boundary=');
    expect(requests[0]!.body).toContain('name="artifact"; filename="survey.dat"');
    expect(requests[0]!.body).toContain('survey contents');
    expect(requests[0]!.body).toContain('name="message"\r\n\r\nUpdated survey');
    await vi.waitFor(() => expect($('#modal_error_txt').text()).toContain('identical'));
    expect($('#message').val()).toBe('Updated survey');
    expect($('#dropzone label').text()).toContain('survey.dat');
    expect(window.location.pathname).toBe('/upload/');
});

it.each([
    ['   ', 'The revision title cannot be empty.'],
    ['x'.repeat(126), 'Maximum 125 characters.'],
])('keeps the selected file and prevents navigation for an invalid title', async (title, error) => {
    $('#message').val(title);
    selectFile();
    const event = new SubmitEvent('submit', { bubbles: true, cancelable: true });
    (document.getElementById('file_upload_form') as HTMLFormElement).dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    expect($('#modal_error_txt').text()).toContain(error);
    expect(requests).toHaveLength(0);
    expect($('#dropzone label').text()).toContain('survey.dat');

    $('#message').val('Corrected title');
    (document.getElementById('file_upload_form') as HTMLFormElement).requestSubmit();
    await vi.waitFor(() => expect($('#modal_error_txt').text()).toContain('identical'));
    expect(requests).toHaveLength(1);
    expect(requests[0]!.body).toContain('survey contents');
    expect(requests[0]!.body).toContain('Corrected title');
});

it('retains the title and files after a failed upload so form submission can retry', async () => {
    responseStatus = 403;
    $('#message').val('Retry this survey');
    selectFile();
    (document.getElementById('file_upload_form') as HTMLFormElement).requestSubmit();
    await vi.waitFor(() => expect($('#modal_error_txt').text()).toBe('Project is locked by another user.'));
    expect($('#loading_spinner').css('display')).toBe('none');
    expect($('#message').val()).toBe('Retry this survey');
    expect($('#dropzone label').text()).toContain('survey.dat');

    responseStatus = 304;
    (document.getElementById('file_upload_form') as HTMLFormElement).requestSubmit();
    await vi.waitFor(() => expect($('#modal_error_txt').text()).toContain('identical'));
    expect(requests).toHaveLength(2);
    for (const request of requests) {
        expect(request.body).toContain('survey contents');
        expect(request.body).toContain('Retry this survey');
    }
});

it.each([
    ['pending', 'Upload saved. The map will update in the background.'],
    ['unavailable', 'Upload saved. Map generation is currently unavailable.'],
    ['skipped', 'The files have been successfully uploaded.'],
    [undefined, 'The files have been successfully uploaded.'],
])('explains successful upload with map status %s and preserves the redirect', (geojson_status, expected) => {
    document.body.insertAdjacentHTML('beforeend', '<div id="modal_success"><p id="modal_success_txt"></p></div>');
    const ajax = vi.spyOn($, 'ajax').mockImplementation(((options: UploadAjaxCallback) => {
        options.success({ browser_url: `${window.location.href}#saved`, geojson_status }, 'success', { status: 200 });
    }) as unknown as JQueryStatic['ajax']);
    let redirect!: () => void;
    const timer = vi.spyOn(window, 'setTimeout').mockImplementation(callback => { redirect = callback as () => void; return 1 as unknown as ReturnType<typeof window.setTimeout>; });
    try {
        $('#message').val('Updated survey');
        selectFile();
        (document.getElementById('file_upload_form') as HTMLFormElement).requestSubmit();
        expect($('#modal_success_txt').text()).toBe(expected);
        expect($('#modal_error_txt').text()).not.toContain('identical');
        expect(timer).toHaveBeenCalledWith(expect.any(Function), 2000);
        redirect();
        expect(window.location.hash).toBe('#saved');
    } finally {
        ajax.mockRestore();
        timer.mockRestore();
    }
});

it('checks count and size limits before accepting files and keeps file names inert', () => {
    const input = (document.getElementById('artifact') as HTMLInputElement);
    function choose(files: File[]) {
        Object.defineProperty(input, 'files', { configurable: true, value: files });
        $('#artifact').triggerHandler('change');
    }
    choose(Array.from({ length: 11 }, (_, index) => new File(['x'], `file-${index}.dat`)));
    expect($('#modal_error_txt').text()).toBe('You can upload a maximum of 10 files at a time.');
    expect($('.remove-file')).toHaveLength(0);
    const large = new File([], 'large.dat');
    Object.defineProperty(large, 'size', { value: 2 * 1024 * 1024 + 1 });
    choose([large]);
    expect($('#modal_error_txt').text()).toBe('File too large: large.dat (Max 2 Mb).');
    const file = new File(['x'], '<img src=x>.dat');
    choose([file]);
    expect($('#dropzone label').text()).toContain(file.name);
    expect($('#dropzone label img')).toHaveLength(0);
    expect(input.value).toBe('');
    $('.remove-file').trigger('click');
    expect($('.remove-file')).toHaveLength(0);
    expect($('#dropzone label').text()).toContain('Please upload up to 10 files');
});

it('waits for future load before wiring and rejects total size as one batch', async () => {
    $('#artifact').off('change');
    const ready = vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const pending = init({ endpoint: '/api/upload/', maxFiles: 10, maxFileSizeMb: 2, maxTotalSizeMb: 1 });
    const file = new File([], 'medium.dat');
    Object.defineProperty(file, 'size', { value: 700_000 });
    Object.defineProperty((document.getElementById('artifact') as HTMLInputElement), 'files', { configurable: true, value: [file, file] });
    $('#artifact').triggerHandler('change');
    expect($('#modal_error_txt').text()).not.toContain('Total upload');
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    $('#artifact').triggerHandler('change');
    expect($('#modal_error_txt').text()).toBe('Total upload size exceeds 1 Mb.');
    expect($('.remove-file')).toHaveLength(0);
    ready.mockRestore();
});

it('keeps repeated submit wiring and delays missing-context failure until submission', async () => {
    const ready = vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    const ajax = vi.spyOn($, 'ajax').mockImplementation(() => ({} as JQuery.jqXHR<unknown>));
    try {
        await init({ endpoint: '/api/upload/', maxFiles: 10, maxFileSizeMb: 2, maxTotalSizeMb: 50 });
        $('#message').val('title');
        $('#file_upload_form').triggerHandler('submit');
        expect(ajax).toHaveBeenCalledTimes(2);
        await expect(init()).resolves.toBeUndefined();
        expect(() => { $('#file_upload_form').triggerHandler('submit'); }).toThrow(TypeError);
    } finally { ajax.mockRestore(); ready.mockRestore(); }
});

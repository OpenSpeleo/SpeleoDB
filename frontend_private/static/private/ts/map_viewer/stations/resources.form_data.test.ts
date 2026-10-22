import { setBrowserUrl, startApiServer, useNativeFetchBodyConstructors } from '../../../../../../frontend_common/test/api-server.ts';
import { StationResources } from './resources.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
let restoreBodyConstructors: () => void;
beforeAll(async () => { originalUrl = window.location.href; server = await startApiServer(); });
beforeEach(() => {
    server.reset();
    setBrowserUrl(`${server.origin}/private/map/`);
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"><div id="station-modal-content"></div>';
    const DOMFormData = FormData;
    restoreBodyConstructors = useNativeFetchBodyConstructors();
    const NativeFormData = FormData;
    const NativeFile = File;
    // JSDOM implements HTML form serialization, but Bun fetch cannot serialize
    // JSDOM's private FormData/File realm. Bun's own FormData has no HTML form
    // constructor. Bridge these real constructors without replacing the form
    // handler, SDK, or transport. Empty files remain entries for the production
    // adapter to omit; replacement bytes have separate native multipart tests.
    globalThis.FormData = class extends NativeFormData {
        constructor(form?: HTMLFormElement) {
            super();
            if (!form) return;
            for (const [name, value] of new DOMFormData(form)) {
                if (typeof value === 'string') this.append(name, value);
                else {
                    if (value.size !== 0) throw new Error('This realm bridge supports only unselected file inputs.');
                    this.append(name, new NativeFile([], value.name, { type: value.type }));
                }
            }
        }
    };
});
afterEach(() => { document.body.innerHTML = ''; restoreBodyConstructors(); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

it.each(['note', 'document'] as const)('submits the real %s edit handler as multipart without disabled or unselected fields', async resource_type => {
    const resource = {
        id: 'resource', resource_type, title: 'Original title', description: 'Original description',
        text_content: resource_type === 'note' ? 'Original note' : '',
        file: resource_type === 'document' ? '/original.txt' : null,
        creation_date: '2026-01-01T12:00:00Z',
    };
    server.handle(request => ({ json: request.method === 'GET' ? [resource] : { ...resource, title: 'Updated café 🦇' } }));
    await StationResources.render('station', document.getElementById('station-modal-content')!);
    StationResources.openEditForm('station', resource.id);
    const form = document.querySelector<HTMLFormElement>('#resource-edit-form')!;
    form.querySelector<HTMLInputElement>('[name="title"]')!.value = 'Updated café 🦇';
    form.querySelector<HTMLTextAreaElement>('[name="description"]')!.value = '';
    const note = form.querySelector<HTMLTextAreaElement>('[name="text_content"]');
    if (note) note.value = 'Updated note café 🦇';
    form.querySelector<HTMLButtonElement>('[type="submit"]')!.click();
    // Completion includes the real handler's subsequent GET/render, preventing
    // pending work from leaking into the next case or a restored body realm.
    await vi.waitFor(() => expect(document.querySelector('#resource-edit-form')).toBeNull());
    expect(server.requests.map(({ method }) => method)).toEqual(['GET', 'PATCH', 'GET']);
    const request = server.requests[1]!;
    expect(request).toMatchObject({
        method: 'PATCH', path: '/api/v2/resources/resource/',
        headers: { 'x-csrftoken': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' },
    });
    expect(request.headers['content-type']).toMatch(/^multipart\/form-data; boundary=/);
    expect(request.body).toContain('name="title"\r\n\r\nUpdated café 🦇');
    expect(request.body).toContain('name="description"\r\n\r\n\r\n');
    for (const absent of ['resource_type', 'file', 'miniature']) {
        expect(request.body).not.toContain(`name="${absent}"`);
    }
    if (resource_type === 'note') expect(request.body).toContain('name="text_content"\r\n\r\nUpdated note café 🦇');
    else expect(request.body).not.toContain('name="text_content"');
});

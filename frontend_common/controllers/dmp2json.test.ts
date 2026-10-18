import { readFileSync } from 'node:fs';
import { startApiServer, setBrowserUrl, loadJQuery, useNativeFetchBodyConstructors } from '../test/api-server.ts';
import { init } from './dmp2json.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let restoreConstructors: () => void;
beforeAll(async () => {
    server = await startApiServer();
    loadJQuery();
    for (const name of ['prism.min.js', 'prism-json.min.js', 'prism-makefile.min.js']) (0, eval)(readFileSync(`frontend_private/static/private/ts/vendors/${name}`, 'utf8'));
});
afterAll(async () => { await server.close(); });
beforeEach(() => {
    server.reset();
    setBrowserUrl(server.origin);
    restoreConstructors = useNativeFetchBodyConstructors();
    document.body.innerHTML = `<div id="fileDropZone"></div><input id="fileInput" type="file"><span id="fileNameDisplay"></span><span id="fileErrorDisplay"></span><button id="downloadBtn"></button><div id="status"></div><div id="loading_spinner" style="display:none"></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><input name="csrfmiddlewaretoken" value="csrf"><div id="resultModal"><div id="codeDisplay"></div><button id="closeModal"></button><button id="copyCodeBtn"></button><button id="downloadCodeBtn"></button></div>`;
    init();
});
afterEach(() => {
    $(window).off('load'); $(document).off('click keydown'); $('body').off('click');
    restoreConstructors(); document.body.replaceChildren(); delete window.surveyData;
});
function choose(name = 'survey.dmp') {
    const file = new File(['survey bytes'], name);
    Object.defineProperty(document.getElementById('fileInput')!, 'files', { configurable: true, value: [file] });
    $('#fileInput').trigger('change');
}

it('uses the real file picker, rejecting invalid extensions before any API request', () => {
    choose('survey.txt');
    expect($('#fileErrorDisplay').text()).toContain('Invalid file type');
    $('#downloadBtn').trigger('click');
    expect(server.requests).toHaveLength(0);
});
it('posts a real multipart file and renders the generated JSON response safely', async () => {
    server.reply({ text: JSON.stringify({ name: '<unsafe>', shots: [] }, null, 2), headers: { 'Content-Type': 'application/octet-stream' } });
    choose();
    $('#downloadBtn').trigger('click');
    expect($('#downloadBtn').prop('disabled')).toBe(true);
    await vi.waitFor(() => { expect($('#resultModal').hasClass('show')).toBe(true); });
    expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/tools/dmp2json/' });
    expect(server.requests[0]!.headers['x-csrftoken']).toBe('csrf');
    expect(server.requests[0]!.body).toContain('filename="survey.dmp"');
    expect($('#codeDisplay code').text()).toBe(JSON.stringify({ name: '<unsafe>', shots: [] }, null, 2));
    expect($('#codeDisplay unsafe')).toHaveLength(0);
    expect($('#downloadBtn').prop('disabled')).toBe(false);
    $('#codeDisplay').trigger('mousedown'); $('#resultModal').trigger('click');
    expect($('#resultModal').hasClass('show')).toBe(true);
    $('#resultModal').trigger('mousedown').trigger('click');
    expect($('#resultModal').hasClass('show')).toBe(false);
});
it('renders HTTP validation errors as text and re-enables conversion', async () => {
    server.reply({ status: 400, json: { error: '<unsafe>' } });
    choose(); $('#downloadBtn').trigger('click');
    await vi.waitFor(() => { expect($('#modal_error_txt').text()).toBe('<unsafe>'); });
    expect($('#modal_error_txt unsafe')).toHaveLength(0);
    expect($('#downloadBtn').prop('disabled')).toBe(false);
});

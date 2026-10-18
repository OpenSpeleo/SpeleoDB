import { startApiServer, setBrowserUrl, loadJQuery, useNativeFetchBodyConstructors } from '../test/api-server.ts';
import { init } from './dmp-doctor.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let restoreConstructors: () => void;
beforeAll(async () => {
    server = await startApiServer();
    loadJQuery();

});
afterAll(async () => { await server.close(); });
beforeEach(() => {
    server.reset();
    setBrowserUrl(server.origin);
    restoreConstructors = useNativeFetchBodyConstructors();
    document.body.innerHTML = `<div id="fileDropZone"></div><input id="fileInput" type="file"><span id="fileNameDisplay"></span><span id="fileErrorDisplay"></span><input id="surveyDate"><input id="surveyDateUncorrupt"><input id="fixDmpSwitch" type="checkbox"><input id="depthUnitSwitch" type="checkbox" checked><input id="reverseDirectionSwitch" type="checkbox"><input id="lengthScaling" value="100"><input id="compassOffset" value="0"><input id="depthOffset" value="0"><span id="depthUnitSuffix"></span><button class="tab-button" data-tab="uncorrupt"></button><button class="tab-button" data-tab="adjust"></button><div class="tab-content" id="tab-uncorrupt"></div><div class="tab-content" id="tab-adjust"></div><button id="resetFormBtn"></button><button id="downloadBtn"></button><div id="status"></div><div id="loading_spinner" style="display:none"></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><input name="csrfmiddlewaretoken" value="csrf">`;
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

it('keeps date limits, tab resets, and file reset behavior', () => {
    expect($('#fixDmpSwitch').prop('checked')).toBe(true);
    expect($('#surveyDate').attr('max')).toBe(new Date().toISOString().split('T')[0]);
    choose(); $('#compassOffset').val('45');
    $('[data-tab="adjust"]').trigger('click');
    expect($('#compassOffset').val()).toBe('0');
    expect($('#fixDmpSwitch').prop('checked')).toBe(false);
    $('#resetFormBtn').trigger('click');
    expect($('#status').text()).toBe('Form reset');
});
it.each([['lengthScaling', '0'], ['compassOffset', '360'], ['depthOffset', '1001']])('rejects invalid %s before transport', (id, value) => {
    choose(); $(`#${id}`).val(value).trigger('input'); $('#downloadBtn').trigger('click');
    expect(server.requests).toHaveLength(0);
    expect($(`#${id}`).hasClass('invalid')).toBe(true);
});
it('sends multipart file and JSON adjustments, then handles the binary download', async () => {
    server.reply({ bytes: new Uint8Array([0, 255, 17]), headers: { 'Content-Type': 'application/octet-stream' } });
    choose(); $('#lengthScaling').val('125'); $('#surveyDateUncorrupt').val('2026-01-01');
    $('#depthUnitSwitch').prop('checked', false).trigger('change');
    $('#downloadBtn').trigger('click');
    await vi.waitFor(() => { expect($('#downloadBtn').prop('disabled')).toBe(false); });
    expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/tools/dmp-doctor/' });
    expect(server.requests[0]!.body).toContain('filename="survey.dmp"');
    expect(server.requests[0]!.body).toContain('"length_scaling":1.25');
    expect(server.requests[0]!.body).toContain('"depth_offset_unit":"meters"');
    expect($('#status').text()).toBe('Download successful!');
    expect($('a')).toHaveLength(0);
});
it('renders HTTP error text and releases the pending button', async () => {
    server.reply({ status: 400, json: { error: '<unsafe>' } });
    choose(); $('#downloadBtn').trigger('click');
    await vi.waitFor(() => { expect($('#modal_error_txt').text()).toBe('<unsafe>'); });
    expect($('#downloadBtn').prop('disabled')).toBe(false);
});

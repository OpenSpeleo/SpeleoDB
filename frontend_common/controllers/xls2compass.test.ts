import { readFileSync } from 'node:fs';
import { startApiServer, setBrowserUrl, loadJQuery, useNativeFetchBodyConstructors } from '../test/api-server.ts';
import { init } from './xls2compass.ts';
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
    document.body.innerHTML = `<input id="caveName" value=" Cave "><input id="surveyName" value=" Survey "><input id="surveyDate" value="2026-01-01"><input id="surveyComment" value=" Comment "><div id="surveyTeamContainer"><input id="surveyTeamInput"></div><div class="location-search-wrapper"><input id="locationSearch"><div id="locationSpinner"></div><div id="locationResults"></div></div><input id="latitude" value="20.5"><input id="longitude" value="-87.2"><span id="latDisplay"></span><span id="lonDisplay"></span><input id="unitSwitch" type="checkbox" checked><span id="metersLabel"></span><span id="feetLabel"></span><table id="dataTable"><tbody><tr><td data-col="station"> A </td><td data-col="depth">10</td></tr></tbody></table><button id="downloadBtn"></button><div id="status"></div><div id="loading_spinner" style="display:none"></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><input name="csrfmiddlewaretoken" value="csrf"><div id="resultModal"><div id="codeDisplay"></div><button id="closeModal"></button><button id="copyCodeBtn"></button><button id="downloadCodeBtn"></button></div>`;
    init();
});
afterEach(() => {
    $(window).off('load'); $(document).off('click keydown'); $('body').off('click');
    restoreConstructors(); document.body.replaceChildren(); delete window.surveyData;
});
function fillShots() {
    $('#dataTable tbody').html('<tr><td data-col="station">A</td><td data-col="depth">10</td><td data-col="length">2</td><td data-col="azimuth">90</td></tr><tr><td data-col="station">B</td><td data-col="depth">12</td></tr>');
}
it('validates metadata and final-row cells before transport', () => {
    fillShots();
    $('#surveyDate').val(''); $('#downloadBtn').trigger('click');
    expect(server.requests).toHaveLength(0);
    expect($('#status').text()).toContain('Survey Date');
    $('#surveyDate').val('2026-01-01');
    $('#dataTable tbody tr:last').append('<td data-col="length">2</td>');
    $('#downloadBtn').trigger('click');
    expect(server.requests).toHaveLength(0);
    expect($('#status').text()).toContain('Some cells are invalid');
});
it('posts generated JSON and preserves conversion output', async () => {
    fillShots();
    server.reply({ text: 'converted', headers: { 'Content-Type': 'application/octet-stream' } });
    $('#unitSwitch').prop('checked', false).trigger('change');
    $('#downloadBtn').trigger('click');
    await vi.waitFor(() => { expect($('#status').text()).toContain('Survey generated successfully'); });
    expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/tools/xls2compass/' });
    expect(server.requests[0]!.headers['x-csrftoken']).toBe('csrf');
    expect(JSON.parse(server.requests[0]!.body)).toMatchObject({ unit: 'meters', survey_date: '2026-01-01', shots: [{ depth: '10', length: '2', azimuth: '90' }, { depth: '12' }] });
    expect($('#codeDisplay code').text()).toBe('converted');
});
it('escapes server validation messages and settles the UI', async () => {
    fillShots();
    server.reply({ status: 400, json: { detail: '<unsafe>' } });
    $('#downloadBtn').trigger('click');
    await vi.waitFor(() => { expect($('#modal_error_txt').text()).toBe('<unsafe>'); });
    expect($('#modal_error_txt unsafe')).toHaveLength(0);
});

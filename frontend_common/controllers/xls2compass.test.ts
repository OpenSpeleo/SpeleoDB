import type { Mock, MockInstance } from 'vitest';
import type { Xls2CompassContext } from '../../ts-types/controllers/xls2compass.ts';
import type { SurveyToolAjaxCall, UploadToolDouble, SurveyTableDouble, ConfiguredSurveyOptions } from '../../ts-types/testing/vitest/survey-tools.ts';
let ajax: Mock<(options: SurveyToolAjaxCall) => unknown>;
let anchorClick: MockInstance<() => void>;
let revokeUrl: Mock<(url: string) => void>;
let objectUrl: Mock<(blob: Blob | MediaSource) => string>;
let writeText: Mock<(text: string) => Promise<void>>;
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initialize } from './xls2compass.ts';
import { attachSurveyTableTool } from '../../frontend_private/static/private/ts/forms/survey_table_tool.ts';
vi.mock('../../frontend_private/static/private/ts/forms/survey_table_tool.ts', () => ({ attachSurveyTableTool: vi.fn() }));
function init(context?: unknown) { return initialize(context as Xls2CompassContext); }
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
let table: SurveyTableDouble;
function options() { return vi.mocked(attachSurveyTableTool).mock.calls.at(-1)![0] as ConfiguredSurveyOptions; }
beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    table = { renderRows: vi.fn(), validateTable: vi.fn(() => true) };
    vi.mocked(attachSurveyTableTool).mockReturnValue(table as unknown as ReturnType<typeof attachSurveyTableTool>);
    ajax = vi.fn(() => ({}));
    vi.spyOn($, 'ajax').mockImplementation(ajax as unknown as JQueryStatic['ajax']);
    anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    objectUrl = vi.fn(() => 'blob:survey');
    window.URL.createObjectURL = objectUrl;
    revokeUrl = vi.fn();
    window.URL.revokeObjectURL = revokeUrl;
    window.Prism = { highlightElement: vi.fn() } as unknown as typeof window.Prism;
    writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    vi.stubGlobal('alert', vi.fn());
    document.body.innerHTML = '<input id="caveName" value=" Cave "><input id="surveyName" value=" Survey "><input id="surveyDate" value="2026-01-01"><input id="surveyComment" value=" Comment "><div id="surveyTeamContainer"><input id="surveyTeamInput"></div><div class="location-search-wrapper"><input id="locationSearch"><div id="locationSpinner"></div><div id="locationResults"></div></div><input id="latitude" value="20.5"><input id="longitude" value="-87.2"><span id="latDisplay"></span><span id="lonDisplay"></span><input id="unitSwitch" type="checkbox" checked><span id="metersLabel"></span><span id="feetLabel"></span><table id="dataTable"><tbody><tr><td data-col="station"> A </td><td data-col="depth">10</td></tr></tbody></table><button id="downloadBtn"></button><div id="status"></div><div id="loading_spinner" style="display:none"></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><input name="csrfmiddlewaretoken" value="csrf"><div id="resultModal"><div id="codeDisplay"></div><button id="closeModal"></button><button id="copyCodeBtn"></button><button id="downloadCodeBtn"></button></div>';
});
afterEach(() => { $(window).off('load'); $(document).off('click keydown'); $('body').off('click'); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); delete (window.URL as unknown as {createObjectURL?: unknown}).createObjectURL; delete (window.URL as unknown as {revokeObjectURL?: unknown}).revokeObjectURL; delete (window as unknown as {Prism?: unknown}).Prism; delete window.surveyData; document.body.innerHTML = ''; });
it('initializes ten columns immediately, preserves station/depth final-row policy and renders empty rows', () => {
    expect(init({ endpoint: '/compass/' })).toBeUndefined();
    expect(options().COLUMNS).toEqual(['station', 'depth', 'length', 'azimuth', 'left', 'right', 'up', 'down', 'flags', 'comment']);
    expect(options().lastRowAllowedColumns).toEqual(['station', 'depth']);
    expect(options().lastRowErrorMessage(['length'])).toBe('Error: The last row should only have Station and Depth. Remove: length.');
    expect(table.renderRows).toHaveBeenCalledExactlyOnceWith([]);
});
it.each([
    ['', 'station', false, false], ['A', 'station', true, true], ['12suffix', 'depth', false, false],
    ['0', 'depth', false, true], ['360', 'azimuth', false, false], ['359', 'azimuth', false, true],
    ['', 'left', false, true], ['1', 'length', true, false], ['', 'length', true, true],
    ['flag', 'flags', false, true], ['flag', 'flags', true, false],
])('preserves strict numeric and final-row validation for %s in %s', (value, column, last, expected) => {
    init({});
    expect(options().validateCell(value, column, last)).toBe(expected);
});
it('preserves its simpler CSV parser and station header detection', () => {
    init({});
    const parse = options().parseClipboardText;
    expect(parse('Station,Depth\r\nA,10\r\nB,20')).toEqual([['A', '10'], ['B', '20']]);
    expect(parse('"A",10')).toEqual([['"A"', '10']]);
    expect(parse('\uFEFFA\t10\n\nB\t20')).toEqual([['A', '10'], ['B', '20']]);
    expect(parse('')).toEqual([]);
});
it('adds distinct trimmed team members safely from keyboard/blur and removes the clicked member', () => {
    init({});
    $('#surveyTeamInput').val(' <Diver> ').trigger($.Event('keydown', { key: 'Enter' }));
    $('#surveyTeamInput').val('<Diver>').trigger('blur');
    $('#surveyTeamInput').val('Other').trigger($.Event('keydown', { key: ',' }));
    expect($('#surveyTeamContainer .tag').length).toBe(2);
    expect($('#surveyTeamContainer .tag span').first().text()).toBe('<Diver>');
    expect($('#surveyTeamContainer Diver').length).toBe(0);
    $('#surveyTeamContainer .tag-remove').first().trigger('click');
    expect($('#surveyTeamContainer .tag span').text()).toBe('Other');
});
it('debounces encoded location requests, safely renders results and selects coordinates', async () => {
    init({});
    $('#locationSearch').val('a').trigger('input');
    await vi.advanceTimersByTimeAsync(500);
    expect(ajax).not.toHaveBeenCalled();
    $('#locationSearch').val('cave & water').trigger('input');
    await vi.advanceTimersByTimeAsync(499);
    expect(ajax).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    const request = ajax.mock.calls[0]![0];
    expect(request.url).toBe('https://nominatim.openstreetmap.org/search?format=json&q=cave%20%26%20water&limit=10&addressdetails=1');
    expect(request.headers).toEqual({ 'User-Agent': 'SpeleoDB Survey Tool' });
    request.success([{ display_name: '<Cave>, Area, Country', lat: '21.5', lon: '-88.25' }]);
    expect($('.location-name').text()).toBe('<Cave>, Area');
    expect($('#locationResults Cave').length).toBe(0);
    $('.location-result-item').trigger('click');
    expect($('#latitude').val()).toBe('21.5');
    expect($('#longitude').val()).toBe('-88.25');
    expect($('#latDisplay').text()).toBe('21.500000');
    expect($('#locationResults').hasClass('show')).toBe(false);
});
it('validates metadata before table cells and displays transport errors literally', () => {
    init({ endpoint: '/compass/' });
    $('#caveName').val('');
    $('#downloadBtn').trigger('click');
    expect(table.validateTable).not.toHaveBeenCalled();
    expect($('#status').text()).toBe('Missing or invalid fields: Cave Name');
    $('#caveName').val('Cave');
    table.validateTable.mockReturnValueOnce(false);
    $('#downloadBtn').trigger('click');
    expect($('#status').text()).toBe('Some cells are invalid. Please correct them before downloading.');
    $('#downloadBtn').trigger('click');
    ajax.mock.calls[0]![0].error({ responseJSON: { detail: '<unsafe>' } }, 'error', 'fallback');
    expect($('#modal_error_txt').text()).toBe('<unsafe>');
    expect($('#modal_error_txt unsafe').length).toBe(0);
});
it('submits exact survey JSON and presents escaped makefile output with form-feed markers', () => {
    init({ endpoint: '/compass/' });
    $('#surveyTeamInput').val('Diver').trigger('blur');
    $('#unitSwitch').prop('checked', false).trigger('change');
    $('#downloadBtn').trigger('click');
    const request = ajax.mock.calls[0]![0];
    expect(request).toMatchObject({ url: '/compass/', method: 'POST', contentType: 'application/json; charset=utf-8', cache: false });
    expect(JSON.parse(request.data as string) as unknown).toEqual({ shots: [{ station: 'A', depth: '10' }], survey_date: '2026-01-01', unit: 'meters', cave_name: 'Cave', survey_name: 'Survey', survey_team: ['Diver'], comment: 'Comment', latitude: 20.5, longitude: -87.2 });
    const xhr = { setRequestHeader: vi.fn() };
    request.beforeSend!(xhr);
    expect(xhr.setRequestHeader).toHaveBeenCalledWith('X-CSRFToken', 'csrf');
    request.success('<survey>\fEND');
    expect(window.surveyData).toBe('<survey>\fEND');
    expect($('#codeDisplay code').text()).toBe('<survey>\fEND');
    expect($('#codeDisplay survey').length).toBe(0);
    expect($('#codeDisplay .ff-char').text()).toBe('\f');
    expect($('#resultModal').hasClass('show')).toBe(true);
    $('#closeModal').trigger('click');
    expect($('#resultModal').hasClass('show')).toBe(false);
});
it('copies and downloads the original text with DAT naming and restores clipboard feedback', async () => {
    init({});
    $('#downloadBtn').trigger('click');
    ajax.mock.calls[0]![0].success('survey-data');
    $('#copyCodeBtn').trigger('click');
    await vi.advanceTimersByTimeAsync(0);
    expect(writeText).toHaveBeenCalledWith('survey-data');
    expect($('#copyCodeBtn').text()).toContain('Copied!');
    await vi.advanceTimersByTimeAsync(2000);
    expect($('#copyCodeBtn').text()).toContain('Copy to Clipboard');
    $('#downloadCodeBtn').trigger('click');
    expect((objectUrl.mock.calls[0]![0] as Blob).type).toBe('text/plain');
    expect((anchorClick.mock.contexts[0] as HTMLAnchorElement).download).toBe('survey.dat');
    expect(revokeUrl).toHaveBeenCalledWith('blob:survey');
});
it('repeats setup and handlers and propagates helper failure', () => {
    init({});
    init({});
    $('#downloadBtn').trigger('click');
    expect(ajax).toHaveBeenCalledTimes(2);
    expect(table.renderRows).toHaveBeenCalledTimes(2);
    const error = new Error('Table failed');
    vi.mocked(attachSurveyTableTool).mockImplementationOnce(() => { throw error; });
    expect(() => init({})).toThrow(error);
});

it('wraps form feeds after Prism without changing original clipboard text', async () => {
    init({});
    vi.mocked(window.Prism.highlightElement).mockImplementationOnce(element => {
        expect($('#resultModal').hasClass('show')).toBe(false);
        expect(element.textContent).toBe('<raw>\f');
        element.innerHTML = '<span class="token">&lt;raw&gt;</span>\f';
    });
    $('#downloadBtn').trigger('click');
    ajax.mock.calls[0]![0].success('<raw>\f');
    expect($('#codeDisplay .token').text()).toBe('<raw>');
    expect($('#codeDisplay .ff-char').text()).toBe('\f');
    $('#copyCodeBtn').trigger('click');
    await vi.advanceTimersByTimeAsync(0);
    expect(writeText).toHaveBeenCalledWith('<raw>\f');
});

it('keeps a drag selection open but closes matching overlay clicks and Escape', () => {
    init({});
    $('#downloadBtn').trigger('click');
    ajax.mock.calls[0]![0].success('survey');
    $('#codeDisplay').trigger('mousedown');
    $('#resultModal').trigger('click');
    expect($('#resultModal').hasClass('show')).toBe(true);
    $('#resultModal').trigger('mousedown').trigger('click');
    expect($('#resultModal').hasClass('show')).toBe(false);
    ajax.mock.calls[0]![0].success('survey');
    $(document).trigger($.Event('keydown', { key: 'Escape' }));
    expect($('#resultModal').hasClass('show')).toBe(false);
});

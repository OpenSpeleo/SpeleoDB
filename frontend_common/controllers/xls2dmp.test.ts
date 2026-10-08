import type { Mock, MockInstance } from 'vitest';
import type { Xls2DmpContext } from '../../ts-types/controllers/xls2dmp.ts';
import type { SurveyToolAjaxCall, UploadToolDouble, SurveyTableDouble, ConfiguredSurveyOptions } from '../../ts-types/testing/vitest/survey-tools.ts';
let ajax: Mock<(options: SurveyToolAjaxCall) => unknown>;
let anchorClick: MockInstance<() => void>;
let revokeUrl: Mock<(url: string) => void>;
let objectUrl: Mock<(blob: Blob | MediaSource) => string>;
let writeText: Mock<(text: string) => Promise<void>>;
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initialize } from './xls2dmp.ts';
import { attachSurveyTableTool } from '../../frontend_private/static/private/ts/forms/survey_table_tool.ts';
vi.mock('../../frontend_private/static/private/ts/forms/survey_table_tool.ts', () => ({ attachSurveyTableTool: vi.fn() }));
function init(context?: unknown) { return initialize(context as Xls2DmpContext); }
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
let table: SurveyTableDouble;
function options() { return vi.mocked(attachSurveyTableTool).mock.calls.at(-1)![0] as ConfiguredSurveyOptions; }
beforeEach(() => {
    vi.clearAllMocks();
    table = { renderRows: vi.fn(), validateTable: vi.fn(() => true) };
    vi.mocked(attachSurveyTableTool).mockReturnValue(table as unknown as ReturnType<typeof attachSurveyTableTool>);
    ajax = vi.fn(() => ({}));
    vi.spyOn($, 'ajax').mockImplementation(ajax as unknown as JQueryStatic['ajax']);
    anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    objectUrl = vi.fn(() => 'blob:survey');
    window.URL.createObjectURL = objectUrl;
    revokeUrl = vi.fn();
    window.URL.revokeObjectURL = revokeUrl;
    document.body.innerHTML = '<input id="surveyDate" value="2026-01-01"><input id="unitSwitch" type="checkbox" checked><input id="directionSwitch" type="checkbox"><span id="feetLabel"></span><span id="metersLabel"></span><span id="inLabel"></span><span id="outLabel"></span><table id="dataTable"><tbody><tr><td data-col="depth"> 10 </td><td data-col="length">2</td><td data-col="azimuth">0</td></tr></tbody></table><button id="downloadBtn"></button><div id="status"></div><div id="loading_spinner" style="display:none"></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><input name="csrfmiddlewaretoken" value="csrf">';
});
afterEach(() => { $(window).off('load'); $('body').off('click'); vi.restoreAllMocks(); delete (window.URL as unknown as {createObjectURL?: unknown}).createObjectURL; delete (window.URL as unknown as {revokeObjectURL?: unknown}).revokeObjectURL; document.body.innerHTML = ''; });
it('initializes a seven-column table immediately with an empty render and depth-only final row', () => {
    expect(init({ endpoint: '/convert/' })).toBeUndefined();
    expect(options().COLUMNS).toEqual(['depth', 'length', 'azimuth', 'left', 'right', 'up', 'down']);
    expect(options().lastRowAllowedColumns).toEqual(['depth']);
    expect(options().lastRowErrorMessage(['length'])).toBe('Error: The last row should only have Station Depth. Remove: length.');
    expect(table.renderRows).toHaveBeenCalledExactlyOnceWith([]);
    expect($('#surveyDate').attr('max')).toBe(new Date().toISOString().split('T')[0]);
});
it.each([
    ['0', 'depth', false, true], ['12suffix', 'depth', false, true], ['', 'depth', true, false],
    ['-1', 'length', false, false], ['', 'length', true, true], ['1', 'length', true, false],
    ['359.9', 'azimuth', false, true], ['360', 'azimuth', false, false],
    ['', 'left', false, true], ['1', 'left', true, false], ['Infinity', 'depth', false, false],
])('preserves numeric and final-row validation for %s in %s', (value, column, last, expected) => {
    init({});
    expect(options().validateCell(value, column, last)).toBe(expected);
});
it('parses CSV quoting and optional station-number headers without dropping legitimate first data rows', () => {
    init({});
    const parse = options().parseClipboardText;
    expect(parse('Station #,Depth,Length,Azimuth\r\n1,10,2,90\r\n2,12,,')).toEqual([['10', '2', '90'], ['12', '', '']]);
    expect(parse('"10","2","90"\n"12",,')).toEqual([['10', '2', '90'], ['12', '', '']]);
    expect(parse('\uFEFF10\t2\t90\n\n12\t\t')).toEqual([['10', '2', '90'], ['12', '', '']]);
    expect(parse('')).toEqual([]);
});
it('checks table validity before date validity and leaves transport untouched on failures', () => {
    init({});
    table.validateTable.mockReturnValue(false);
    $('#surveyDate').val('');
    $('#downloadBtn').trigger('click');
    expect($('#status').text()).toBe('Some cells are invalid. Please correct them before downloading.');
    table.validateTable.mockReturnValue(true);
    $('#downloadBtn').trigger('click');
    expect($('#status').text()).toBe('Please enter a valid survey date.');
    expect($('#surveyDate').hasClass('invalid-date')).toBe(true);
    expect(ajax).not.toHaveBeenCalled();
});
it('collects trimmed shot values with selected units and direction and sends JSON with CSRF', () => {
    init({ endpoint: '/convert/' });
    $('#unitSwitch').prop('checked', false).trigger('change');
    $('#directionSwitch').prop('checked', true).trigger('change');
    $('#downloadBtn').trigger('click');
    const request = ajax.mock.calls[0]![0];
    expect(request).toMatchObject({ url: '/convert/', method: 'POST', contentType: 'application/json; charset=utf-8', cache: false });
    expect(JSON.parse(request.data as string) as unknown).toEqual({ shots: [{ depth: '10', length: '2', azimuth: '0' }], survey_date: '2026-01-01', unit: 'meters', direction: 'out' });
    const xhr = { setRequestHeader: vi.fn() };
    expect(request.beforeSend!(xhr)).toBe(true);
    expect(xhr.setRequestHeader).toHaveBeenCalledWith('X-CSRFToken', 'csrf');
    request.success('dmp-data');
    expect((anchorClick.mock.contexts[0] as HTMLAnchorElement).download).toBe('survey.dmp');
    expect(revokeUrl).toHaveBeenCalledWith('blob:survey');
    expect($('#status').text()).toBe('Download successful!');
});
it('shows errors as literal text and repeats table setup and submit handlers', () => {
    init({});
    init({});
    $('#downloadBtn').trigger('click');
    expect(ajax).toHaveBeenCalledTimes(2);
    ajax.mock.calls[0]![0].error({ responseText: '<unsafe>' }, 'error', 'fallback');
    expect($('#modal_error_txt').text()).toBe('<unsafe>');
    expect($('#modal_error_txt unsafe').length).toBe(0);
    expect(table.renderRows).toHaveBeenCalledTimes(2);
});
it('propagates helper failure and only dereferences missing context when submitting', () => {
    const error = new Error('Table unavailable');
    vi.mocked(attachSurveyTableTool).mockImplementationOnce(() => { throw error; });
    expect(() => init({})).toThrow(error);
    expect(() => init()).not.toThrow();
    expect(() => $('#downloadBtn').trigger('click')).toThrow(TypeError);
});

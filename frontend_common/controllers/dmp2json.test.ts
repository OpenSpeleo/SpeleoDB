import type { Mock, MockInstance } from 'vitest';
import type { Dmp2JsonContext } from '../../ts-types/controllers/dmp2json.ts';
import type { SurveyToolAjaxCall, UploadToolDouble, SurveyTableDouble, ConfiguredSurveyOptions } from '../../ts-types/testing/vitest/survey-tools.ts';
let ajax: Mock<(options: SurveyToolAjaxCall) => unknown>;
let anchorClick: MockInstance<() => void>;
let revokeUrl: Mock<(url: string) => void>;
let objectUrl: Mock<(blob: Blob | MediaSource) => string>;
let writeText: Mock<(text: string) => Promise<void>>;
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initialize } from './dmp2json.ts';
import { attachToolFileUpload } from '../../frontend_private/static/private/ts/forms/tool_file_upload.ts';
vi.mock('../../frontend_private/static/private/ts/forms/tool_file_upload.ts', () => ({ attachToolFileUpload: vi.fn() }));
function init(context?: unknown) { return initialize(context as Dmp2JsonContext); }
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
let dropzone: UploadToolDouble;
beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    dropzone = { getFile: vi.fn(() => new File(['survey'], 'survey.dmp')), setStatus: vi.fn() } as UploadToolDouble;
    vi.mocked(attachToolFileUpload).mockReturnValue(dropzone);
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
    document.body.innerHTML = '<button id="downloadBtn"></button><div id="status"></div><div id="loading_spinner" style="display:none"></div><div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div><input name="csrfmiddlewaretoken" value="csrf"><div id="resultModal"><div id="codeDisplay"></div><button id="closeModal"></button><button id="copyCodeBtn"></button><button id="downloadCodeBtn"></button></div>';
});
afterEach(() => { $(window).off('load'); $(document).off('keydown'); $('body').off('click'); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); delete (window.URL as unknown as {createObjectURL?: unknown}).createObjectURL; delete (window.URL as unknown as {revokeObjectURL?: unknown}).revokeObjectURL; delete (window as unknown as {Prism?: unknown}).Prism; delete window.surveyData; document.body.innerHTML = ''; });
function convert(response: unknown) { $('#downloadBtn').trigger('click'); ajax.mock.calls.at(-1)![0].success(response); }
it('attaches the DMP upload controller immediately and prevents submission without a file', () => {
    expect(init({ endpoint: '/convert/' })).toBeUndefined();
    expect(vi.mocked(attachToolFileUpload).mock.calls[0]![0].allowedExtensions).toEqual(['dmp']);
    dropzone.getFile.mockReturnValue(null);
    $('#downloadBtn').trigger('click');
    expect(dropzone.setStatus).toHaveBeenCalledWith('Please select a DMP file first.', 'red', 'bold');
    expect(ajax).not.toHaveBeenCalled();
});
it('submits multipart without serialization, sets CSRF and shows escaped JSON with Prism', () => {
    init({ endpoint: '/convert/' });
    $('#downloadBtn').trigger('click');
    const request = ajax.mock.calls[0]![0];
    expect(request).toMatchObject({ url: '/convert/', method: 'POST', processData: false, contentType: false, cache: false });
    expect(((request.data as FormData).get('file') as File).name).toBe('survey.dmp');
    const xhr = { setRequestHeader: vi.fn() };
    expect(request.beforeSend!(xhr)).toBe(true);
    expect(xhr.setRequestHeader).toHaveBeenCalledWith('X-CSRFToken', 'csrf');
    request.success({ name: '<unsafe>' });
    expect(window.surveyData).toBe(JSON.stringify({ name: '<unsafe>' }, null, 2));
    expect($('#codeDisplay code').text()).toBe(window.surveyData);
    expect($('#codeDisplay unsafe').length).toBe(0);
    expect(window.Prism.highlightElement).toHaveBeenCalledWith($('#codeDisplay code')[0]);
    expect($('#resultModal').hasClass('show')).toBe(true);
    expect($('#downloadBtn').prop('disabled')).toBe(false);
});
it('preserves string responses and requires a matching overlay mousedown and click to close', () => {
    init({});
    convert('{ "raw": 1 }');
    expect(window.surveyData).toBe('{ "raw": 1 }');
    $('#resultModal').trigger('click');
    expect($('#resultModal').hasClass('show')).toBe(true);
    $('#codeDisplay').trigger('mousedown');
    $('#resultModal').trigger('click');
    expect($('#resultModal').hasClass('show')).toBe(true);
    $('#resultModal').trigger('mousedown').trigger('click');
    expect($('#resultModal').hasClass('show')).toBe(false);
    convert('{}');
    $(document).trigger($.Event('keydown', { key: 'Escape' }));
    expect($('#resultModal').hasClass('show')).toBe(false);
});
it('copies original code, restores the label after two seconds and reports clipboard rejection', async () => {
    init({});
    convert('raw');
    $('#copyCodeBtn').trigger('click');
    await vi.advanceTimersByTimeAsync(0);
    expect(writeText).toHaveBeenCalledWith('raw');
    expect($('#copyCodeBtn').text()).toContain('Copied!');
    await vi.advanceTimersByTimeAsync(2000);
    expect($('#copyCodeBtn').text()).toContain('Copy to Clipboard');
    writeText.mockRejectedValueOnce(new Error('Denied'));
    $('#copyCodeBtn').trigger('click');
    await vi.advanceTimersByTimeAsync(0);
    expect(alert).toHaveBeenCalledWith('Failed to copy to clipboard');
});
it('downloads original code as JSON and revokes and removes the temporary URL and link', () => {
    init({});
    convert('raw');
    $('#downloadCodeBtn').trigger('click');
    expect((objectUrl.mock.calls[0]![0] as Blob).type).toBe('application/json');
    expect((anchorClick.mock.contexts[0] as HTMLAnchorElement).download).toBe('survey.json');
    expect(revokeUrl).toHaveBeenCalledWith('blob:survey');
    expect($('a').length).toBe(0);
});
it.each([{ responseJSON: { error: '<unsafe>' } }, { responseText: '{"message":"<unsafe>"}' }, { responseText: '<unsafe>' }])('renders transport errors as text and restores controls', xhr => {
    init({});
    $('#downloadBtn').trigger('click');
    ajax.mock.calls[0]![0].error(xhr, 'error', 'fallback');
    expect($('#modal_error_txt').text()).toBe('<unsafe>');
    expect($('#modal_error_txt unsafe').length).toBe(0);
    expect($('#downloadBtn').prop('disabled')).toBe(false);
});
it('repeats conversion handlers and propagates unavailable highlighting at the success callback', () => {
    init({});
    init({});
    $('#downloadBtn').triggerHandler('click');
    expect(ajax).toHaveBeenCalledTimes(2);
    delete (window as unknown as {Prism?: unknown}).Prism;
    expect(() => ajax.mock.calls[0]![0].success('{}')).toThrow(TypeError);
});

it('keeps each initialization’s original result separate despite shared modal DOM', async () => {
    init({});
    init({});
    $('#downloadBtn').trigger('click');
    ajax.mock.calls[0]![0].success('first');
    ajax.mock.calls[1]![0].success('second');
    $('#copyCodeBtn').trigger('click');
    await vi.advanceTimersByTimeAsync(0);
    expect(writeText.mock.calls).toEqual([['first'], ['second']]);
    expect($('#codeDisplay code').text()).toBe('second');
});

it('preserves the original response when Prism fails and does not open the modal', async () => {
    init({});
    const failure = new Error('Highlighter unavailable');
    vi.mocked(window.Prism.highlightElement).mockImplementationOnce(() => { throw failure; });
    expect(() => convert('<raw>\f')).toThrow(failure);
    expect($('#resultModal').hasClass('show')).toBe(false);
    expect($('#codeDisplay code').text()).toBe('<raw>\f');
    expect($('#codeDisplay .ff-char')).toHaveLength(0);
    $('#copyCodeBtn').trigger('click');
    await vi.advanceTimersByTimeAsync(0);
    expect(writeText).toHaveBeenCalledWith('<raw>\f');
});

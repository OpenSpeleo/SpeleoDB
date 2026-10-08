import type { RevisionCommit } from '../../ts-types/domain/project-presentation.ts';
import type { RevisionHistoryContext } from '../../ts-types/controllers/revision-history.ts';
import type { Mock } from 'vitest';
import type { ControllerAjaxCall } from '../../ts-types/testing/vitest/controller-ajax.ts';
let ajax: Mock<(options: ControllerAjaxCall) => {responseJSON?: unknown}>;
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initialize } from './revision-history.ts';
function init(context?: unknown) { return initialize(context as RevisionHistoryContext); }
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
let commits: RevisionCommit[];
beforeEach(() => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    commits = [{ id: '1234567890', message: '<message>', author_name: '<Diver>', authored_date: '2026/01/01', url: 'javascript:bad', formats: [{ name: '<DMP>', download_url: '/survey.dmp' }] }];
    ajax = vi.fn(options => { options.success({ commits }); return {}; });
    vi.spyOn($, 'ajax').mockImplementation(ajax as unknown as JQueryStatic['ajax']);
    document.body.innerHTML = '<div id="loading_spinner"></div><div id="mobile-revision-container"></div><table><tbody id="commit-table-container"><tr id="commit-template" style="display:none"><td><span class="font-medium"></span></td><td><span class="font-medium"></span></td><td><span class="text-center"></span></td><td><span class="font-medium"></span></td><td><a class="revision_explorer"></a><ul id="format-download-container"><li id="format-download-template" style="display:none"><a></a></li></ul></td></tr></tbody></table>';
});
afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ''; });
it('waits for load then uses synchronous AJAX and renders independent mobile and desktop rows', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const pending = init({ endpoint: '/revisions/' });
    expect(ajax).not.toHaveBeenCalled();
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    expect(ajax.mock.calls[0]![0]).toMatchObject({ url: '/revisions/', type: 'GET', dataType: 'json', async: false });
    expect($('.revision-id').text()).toBe('12345678');
    expect($('.revision-message').text()).toBe('<message>');
    expect($('#commit-table-container tr').length).toBe(1);
    expect($('#commit-template').length).toBe(0);
    expect($('#format-download-template').length).toBe(0);
    expect($('.revision-actions [data-speleodb-scope]').attr('data-speleodb-bind')).toBe('revision-controllers-revision-history-1');
    expect($('.revision-actions a').first().text()).toBe('<DMP>');
    expect($('#mobile-revision-container message').length).toBe(0);
    expect($('.revision_explorer').attr('href')).not.toContain('javascript:');
    expect($('#loading_spinner')[0]!.style.display).toBe('none');
});
it('skips only the exact automated project creation pair', async () => {
    commits.push({ ...commits[0]!, author_name: 'SpeleoDB', message: '[Automated] Project Creation' });
    commits.push({ ...commits[0]!, author_name: 'Diver', message: '[Automated] Project Creation', formats: [] });
    await init({ endpoint: '/revisions/' });
    expect($('.revision-item').length).toBe(2);
    expect($('#commit-table-container tr').length).toBe(2);
});
it('repeated initialization appends mobile rows after removing its sole desktop template', async () => {
    await init({ endpoint: '/revisions/' });
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await init({ endpoint: '/revisions/' });
    expect($('.revision-item').length).toBe(2);
    expect($('#commit-table-container tr').length).toBe(1);
    expect(console.error).toHaveBeenCalledWith('#format-download-template not found.');
});
it('logs transport failures and hides the spinner without rejecting initialization', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    ajax.mockImplementation(options => { options.error('offline', 'failed'); return {}; });
    await expect(init({ endpoint: '/revisions/' })).resolves.toBeUndefined();
    expect(console.error).toHaveBeenCalledWith('ERROR: offline & failed');
    expect($('#loading_spinner')[0]!.style.display).toBe('none');
});
it('rejects malformed commit formats and missing context', async () => {
    delete (commits[0] as Partial<RevisionCommit>).formats;
    await expect(init({ endpoint: '/revisions/' })).rejects.toThrow(TypeError);
    await expect(init()).rejects.toThrow(TypeError);
});

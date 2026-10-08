import type { GitTreeResponse, GitTreeFile } from '../../ts-types/domain/project-presentation.ts';
import type { MomentRuntime, MomentValue } from '../../ts-types/browser/moment.d.ts';
interface FakeMoment extends MomentValue { value: string }
import type { GitViewContext } from '../../ts-types/controllers/git-view.ts';
import type { Mock } from 'vitest';
import type { ControllerAjaxCall } from '../../ts-types/testing/vitest/controller-ajax.ts';
let ajax: Mock<(options: ControllerAjaxCall) => {responseJSON?: unknown}>;
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initialize } from './git-view.ts';
function init(context?: unknown) { return initialize(context as GitViewContext); }
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
function file(path: string, date = '2026/01/01 12:00'): GitTreeFile {
    return { path, name: path.split('/').at(-1)!, size: '42 B', download_url: '/download/', commit: { message: path, url: '/commit/', dt_since: 'today', authored_date: date } };
}
let response: GitTreeResponse;
beforeEach(() => {
    response = { commit: { author_name: 'Diver', message: '<unsafe>', hexsha_short: '123', dt_since: 'today' }, project: { n_commits: 7 }, files: [file('z.dat'), file('folder/old.dat'), file('a.dat'), file('folder/new.dat', '2026/02/01 12:00')] };
    ajax = vi.fn(options => { options.success(response); return { responseJSON: response }; });
    vi.spyOn($, 'ajax').mockImplementation(ajax as unknown as JQueryStatic['ajax']);
    window.moment = vi.fn((value: string): FakeMoment => ({ isAfter: (previous: MomentValue) => value > (previous as FakeMoment).value, value })) as MomentRuntime;
    document.body.innerHTML = '<div id="loading_spinner"></div><span id="commit-author"></span><span id="commit-message"></span><span id="commit-hexsha_short"></span><span id="commit-dt_since"></span><span id="n-commits-count"></span><div id="row-template-currentdir" style="display:none"><span class="current-gitfolder-name"></span></div><div id="row-template-folder" style="display:none"><button class="gitfolder-link"><span class="gitfolder-name"></span></button><a class="commit-message"></a><a class="commit-time-ago"></a></div><div id="row-template-file" style="display:none"><a class="download-file-link"><span class="download-file-name"></span></a><a class="file-size-link"><span class="file-size"></span></a><a class="commit-message"></a><a class="commit-time-ago"></a></div><div id="git-viewer-container"></div>';
});
afterEach(() => { vi.restoreAllMocks(); delete (window as unknown as {moment?: MomentRuntime}).moment; document.body.innerHTML = ''; });
it('fetches synchronously immediately, renders metadata as text and sorts files', () => {
    expect(init({ endpoint: '/tree/' })).toBeUndefined();
    expect(ajax.mock.calls[0]![0]).toMatchObject({ url: '/tree/', type: 'GET', dataType: 'json', async: false });
    expect($('#commit-message').text()).toBe('<unsafe>');
    expect($('#commit-message unsafe').length).toBe(0);
    expect($('#n-commits-count').text()).toBe('7');
    expect($('#git-viewer-container .download-file-name').map(function () { return $(this).text(); }).get()).toEqual(['a.dat', 'z.dat']);
    expect($('#git-viewer-container .gitfolder-name').text()).toBe('folder');
    expect($('#git-viewer-container .commit-message').first().text()).toBe('folder/new.dat');
    expect($('#loading_spinner')[0]!.style.display).toBe('none');
});
it('navigates into folders and back using the clicked row without refetching', () => {
    init({ endpoint: '/tree/' });
    $('#git-viewer-container .gitfolder-link').trigger('click');
    expect($('#git-viewer-container .current-gitfolder-name').text()).toBe('Current Folder: /folder');
    expect($('#git-viewer-container .gitfolder-name').text()).toBe('..');
    expect($('#git-viewer-container .download-file-name').map(function () { return $(this).text(); }).get()).toEqual(['new.dat', 'old.dat']);
    $('#git-viewer-container .gitfolder-link').trigger('click');
    expect($('#git-viewer-container .current-gitfolder-name').text()).toBe('Current Folder: /');
    expect(ajax).toHaveBeenCalledOnce();
});
it('sanitizes download and commit URLs while preserving literal file names', () => {
    response.files = [{ ...file('<b>file</b>'), name: '<b>file</b>', path: 'file', download_url: 'javascript:alert(1)', commit: { ...file('file').commit, url: 'javascript:alert(1)' } }];
    init({ endpoint: '/tree/' });
    expect($('#git-viewer-container .download-file-name').text()).toBe('<b>file</b>');
    expect($('#git-viewer-container b').length).toBe(0);
    expect($('#git-viewer-container .download-file-link').attr('href')).not.toContain('javascript:');
    expect($('#git-viewer-container .commit-message').attr('href')).not.toContain('javascript:');
});
it('hides loading on AJAX errors and repeats requests without duplicating the rendered tree', () => {
    init({ endpoint: '/tree/' });
    init({ endpoint: '/tree/' });
    expect($('#git-viewer-container .current-gitfolder-name').length).toBe(1);
    vi.spyOn(console, 'log').mockImplementation(() => {});
    ajax.mockImplementation(options => { options.error('failure', 'offline'); return {}; });
    expect(() => init({ endpoint: '/tree/' })).not.toThrow();
    expect(console.log).toHaveBeenCalledWith('ERROR: failure & offline');
    expect($('#loading_spinner')[0]!.style.display).toBe('none');
});
it('throws synchronously for missing context and leaves loading shown', () => {
    expect(() => init()).toThrow(TypeError);
    expect($('#loading_spinner')[0]!.style.display).not.toBe('none');
});

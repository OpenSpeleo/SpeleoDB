import type { GitTreeFile, GitTreeResponse } from '../../ts-types/domain/project-presentation.ts';
import { readFileSync } from 'node:fs';
import { init } from './git-view.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });
const commit = { author_name: 'Diver', author_email: 'diver@example.test', authored_date: '2026/01/01 12:00', committer_name: 'Diver', committer_email: 'diver@example.test', committed_date: '2026/01/01 12:00', dt_since: 'today', hexsha: '123456789', hexsha_short: '123', message: '<unsafe>', parents: [], url: '/commit/', formats: [] };
function file(path: string, date = '2026/01/01 12:00'): GitTreeFile {
    return { hexsha: 'file-sha', path, name: path.split('/').at(-1)!, size: '42 B', download_url: '/download/', commit: { ...commit, message: path, authored_date: date } };
}
let response: GitTreeResponse;
beforeEach(() => {
    response = { commit, project: { id: 'project', country: 'US', visibility: 'PRIVATE', commit_count: 7, latest_commit: null, active_mutex: null, created_by: 'diver@example.test', n_commits: 7, type: 'COMPASS', name: 'Cave', description: '', color: '#000000', exclude_geojson: false, is_active: true, creation_date: '2026-01-01', modified_date: '2026-01-01', fork_from: null }, files: [file('z.dat'), file('folder/old.dat'), file('a.dat'), file('folder/new.dat', '2026/02/01 12:00')] };
    server.handle(() => ({ json: response }));
    (0, eval)(readFileSync('frontend_private/static/private/ts/vendors/moment.js', 'utf8'));
    document.body.innerHTML = '<div id="loading_spinner"></div><span id="commit-author"></span><span id="commit-message"></span><span id="commit-hexsha_short"></span><span id="commit-dt_since"></span><span id="n-commits-count"></span><div id="row-template-currentdir" style="display:none"><span class="current-gitfolder-name"></span></div><div id="row-template-folder" style="display:none"><button class="gitfolder-link"><span class="gitfolder-name"></span></button><a class="commit-message"></a><a class="commit-time-ago"></a></div><div id="row-template-file" style="display:none"><a class="download-file-link"><span class="download-file-name"></span></a><a class="file-size-link"><span class="file-size"></span></a><a class="commit-message"></a><a class="commit-time-ago"></a></div><div id="git-viewer-container"></div>';
});
afterEach(() => { vi.restoreAllMocks(); delete (window as unknown as {moment?: unknown}).moment; document.body.innerHTML = ''; });
it('loads the generated Git tree asynchronously, renders text metadata and sorts files', async () => {
    await init({ projectId: 'project', commit: 'latest' });
    expect(server.requests[0]).toMatchObject({ method: 'GET', path: '/api/v2/projects/project/git_explorer/latest/' });
    expect($('#commit-message').text()).toBe('<unsafe>');
    expect($('#commit-message unsafe').length).toBe(0);
    expect($('#n-commits-count').text()).toBe('7');
    expect($('#git-viewer-container .download-file-name').map(function () { return $(this).text(); }).get()).toEqual(['a.dat', 'z.dat']);
    expect($('#git-viewer-container .gitfolder-name').text()).toBe('folder');
    expect($('#git-viewer-container .commit-message').first().text()).toBe('folder/new.dat');
    expect($('#loading_spinner')[0]!.style.display).toBe('none');
});
it('navigates into folders and back using the clicked row without refetching', async () => {
    await init({ projectId: 'project', commit: 'latest' });
    $('#git-viewer-container .gitfolder-link').trigger('click');
    expect($('#git-viewer-container .current-gitfolder-name').text()).toBe('Current Folder: /folder');
    expect($('#git-viewer-container .gitfolder-name').text()).toBe('..');
    expect($('#git-viewer-container .download-file-name').map(function () { return $(this).text(); }).get()).toEqual(['new.dat', 'old.dat']);
    $('#git-viewer-container .gitfolder-link').trigger('click');
    expect($('#git-viewer-container .current-gitfolder-name').text()).toBe('Current Folder: /');
    expect(server.requests).toHaveLength(1);
});
it('sanitizes download and commit URLs while preserving literal file names', async () => {
    response.files = [{ ...file('<b>file</b>'), name: '<b>file</b>', path: 'file', download_url: 'javascript:alert(1)', commit: { ...file('file').commit, url: 'javascript:alert(1)' } }];
    await init({ projectId: 'project', commit: 'latest' });
    expect($('#git-viewer-container .download-file-name').text()).toBe('<b>file</b>');
    expect($('#git-viewer-container b').length).toBe(0);
    expect($('#git-viewer-container .download-file-link').attr('href')).not.toContain('javascript:');
    expect($('#git-viewer-container .commit-message').attr('href')).not.toContain('javascript:');
});
it('hides loading after an HTTP error and allows a fresh initialization', async () => {
    server.reply({ status: 403, json: { detail: 'Denied' } });
    await expect(init({ projectId: 'project', commit: 'latest' })).resolves.toBeUndefined();
    expect($('#loading_spinner')[0]!.style.display).toBe('none');
    expect($('#git-viewer-container .download-file-name')).toHaveLength(0);
    server.reply({ json: response });
    await init({ projectId: 'project', commit: 'latest' });
    expect($('#git-viewer-container .current-gitfolder-name')).toHaveLength(1);
});

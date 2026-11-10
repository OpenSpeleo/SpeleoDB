import type { RevisionCommit } from '../../ts-types/domain/project-presentation.ts';
import { init } from './revision-history.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });
let commits: RevisionCommit[];
beforeEach(() => {
    commits = [{ id: '1234567890', message: '<message>', author_name: '<Diver>', authored_date: '2026-01-01T12:00:00Z', author_email: 'diver@example.com', dt_since: '1 day', parent_ids: [], tree: [], url: 'javascript:bad', formats: [{ name: '<DMP>', download_url: '/survey.dmp' }] }];
    server.handle(() => ({ json: { commits } }));
    document.body.innerHTML = '<div id="loading_spinner"></div><div id="mobile-revision-container"></div><table><tbody id="commit-table-container"><tr id="commit-template" style="display:none"><td><span class="font-medium"></span></td><td><span class="font-medium"></span></td><td><span class="text-center"></span></td><td><span class="font-medium"></span></td><td><span class="revision-map-slot"></span><a class="revision_explorer"></a><ul id="format-download-container"><li id="format-download-template" style="display:none"><a></a></li></ul></td></tr></tbody></table>';
});
afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ''; });
it('waits for load then uses the generated operation and renders independent mobile and desktop rows', async () => {
    // JSDOM's read-only document state cannot revisit an unfinished page load.
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const pending = init({ projectId: 'project', revisionMapUrls: {} });
    expect(server.requests).toHaveLength(0);
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    expect(server.requests[0]).toMatchObject({ method: 'GET', path: '/api/v2/projects/project/revisions/' });
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
    await init({ projectId: 'project', revisionMapUrls: {} });
    expect($('.revision-item').length).toBe(2);
    expect($('#commit-table-container tr').length).toBe(2);
});
it.each(['2026-11-10T08:18:00Z', '2026-07-10T08:18:00Z'])(
    'displays %s in the browser timezone without a timezone suffix on mobile and desktop', async authoredDate => {
        commits[0]!.authored_date = authoredDate;
        await init({ projectId: 'project', revisionMapUrls: {} });
        const mobileDate = $('.revision-meta-item').last().find('span').text();
        const desktopDate = $('#commit-table-container tr').first().find('td').eq(2).text();
        const date = new Date(authoredDate);
        const hour = date.getHours();
        const minute = String(date.getMinutes()).padStart(2, '0');
        expect(mobileDate).toBe(desktopDate);
        expect(mobileDate).not.toMatch(/\b(?:GMT|UTC)\b/);
        expect(mobileDate).toMatch(new RegExp(`\\b0?(?:${hour}|${hour % 12 || 12}):${minute}\\b`));
        expect(mobileDate).not.toContain(authoredDate);
    },
);
it('repeated initialization appends mobile rows after removing its sole desktop template', async () => {
    await init({ projectId: 'project', revisionMapUrls: {} });
    vi.spyOn(console, 'error');
    await init({ projectId: 'project', revisionMapUrls: {} });
    expect($('.revision-item').length).toBe(2);
    expect($('#commit-table-container tr').length).toBe(1);
    expect(console.error).toHaveBeenCalledWith('#format-download-template not found.');
});
it('hides the spinner on HTTP errors without rejecting initialization', async () => {
    server.reply({ status: 403, json: { detail: 'Denied' } });
    await expect(init({ projectId: 'project', revisionMapUrls: {} })).resolves.toBeUndefined();
    expect($('#loading_spinner')[0]!.style.display).toBe('none');
    expect($('.revision-item')).toHaveLength(0);
});
it('offers exact historical maps on desktop and mobile and marks missing artifacts unavailable', async () => {
    const sha = 'a'.repeat(40);
    commits[0] = { ...commits[0]!, id: sha };
    commits.push({ ...commits[0], id: 'b'.repeat(40) });
    const url = `/private/project/project/revisions/${sha}/map/`;
    await init({ projectId: 'project', revisionMapUrls: { [sha]: url } });
    for (const container of ['#mobile-revision-container', '#commit-table-container']) {
        const links = $(`${container} a.revision-map`);
        expect(links).toHaveLength(1);
        expect(links.attr('href')).toBe(url);
        expect(links.attr('target')).toBe('_blank');
        expect(links.attr('rel')).toContain('noopener');
        expect($(`${container} .revision-map-unavailable`)).toHaveLength(1);
    }
});

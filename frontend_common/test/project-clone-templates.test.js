import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initGitView } from '../controllers/git-view.js';
import { init as initRevisionHistory } from '../controllers/revision-history.js';

const root = process.cwd();
const jquery = readFileSync(resolve(root, 'frontend_public/static/js/vendors/jquery-3.7.1.js'), 'utf8');

function mountPage(page) {
    const template = readFileSync(resolve(root, `frontend_private/templates/pages/project/${page}.html`), 'utf8');
    // Only static clone sources and their containers are used by these controllers.
    document.body.innerHTML = template.replace(/{%.*?%}/gs, '');
    const style = document.createElement('style');
    style.textContent = readFileSync(resolve(root, `frontend_common/styles/templates/frontend-private-templates-pages-project-${page.replaceAll('_', '-')}.css`), 'utf8');
    document.head.append(style);
}

function respondWith(data) {
    vi.spyOn($, 'ajax').mockImplementation(options => {
        options.success(data);
        return { responseJSON: data };
    });
}

beforeAll(() => {
    (0, eval)(jquery);
});

afterEach(() => {
    vi.restoreAllMocks();
    document.head.innerHTML = '';
    document.body.innerHTML = '';
});

it('git browser hides its sources while displaying cloned rows across folder navigation', () => {
    mountPage('git_view');
    const sources = Array.from(document.querySelectorAll('[id^="row-template-"]'));
    expect(sources).toHaveLength(3);
    sources.forEach(source => expect(getComputedStyle(source).display).toBe('none'));
    const commit = {
        author_name: 'Surveyor', message: 'Updated survey', hexsha_short: 'abc123',
        dt_since: '1 day ago', authored_date: '2026/09/15 10:00', url: '/revision/abc123/',
    };
    respondWith({
        commit,
        project: { n_commits: 1 },
        files: [
            { name: 'notes.txt', path: 'notes.txt', size: '12 B', download_url: '/download/notes.txt', commit },
            { name: 'survey.dat', path: 'surveys/survey.dat', size: '24 B', download_url: '/download/survey.dat', commit },
        ],
    });
    initGitView({ endpoint: '/git-tree/' });
    const container = document.getElementById('git-viewer-container');
    const expectVisibleRows = () => {
        expect(container.children).toHaveLength(3);
        Array.from(container.children).forEach(row => {
            expect(row.id).toBe('');
            expect(getComputedStyle(row).display).not.toBe('none');
        });
        sources.forEach(source => expect(getComputedStyle(source).display).toBe('none'));
    };
    expectVisibleRows();
    expect(container.querySelector('.download-file-name').textContent).toBe('notes.txt');
    container.querySelector('.gitfolder-link').click();
    expectVisibleRows();
    expect(container.querySelector('.current-gitfolder-name').textContent).toBe('Current Folder: /surveys');
    expect(container.querySelector('.download-file-link').getAttribute('href')).toBe('/download/survey.dat');
    expect(container.querySelector('.gitfolder-name').textContent).toBe('..');
    container.querySelector('.gitfolder-link').click();
    expectVisibleRows();
    expect(container.querySelector('.download-file-name').textContent).toBe('notes.txt');
});

it('revision history displays commit and download clones after removing source IDs', async () => {
    mountPage('revision_history');
    for (const id of ['commit-template', 'format-download-template']) {
        expect(getComputedStyle(document.getElementById(id)).display).toBe('none');
    }
    respondWith({
        commits: [
            {
                id: 'abc123456789', author_name: 'Surveyor', authored_date: '2026/09/15',
                message: 'First survey', url: '/revision/abc123/',
                formats: [
                    { name: 'Compass', download_url: '/download/compass/' },
                    { name: 'Survex', download_url: '/download/survex/' },
                ],
            },
            {
                id: 'def123456789', author_name: 'Surveyor', authored_date: '2026/09/14',
                message: 'Notes only', url: '/revision/def123/', formats: [],
            },
        ],
    });
    const initialization = initRevisionHistory({ endpoint: '/revisions/' });
    window.dispatchEvent(new Event('load'));
    await initialization;
    const rows = document.querySelectorAll('#commit-table-container > tr');
    expect(rows).toHaveLength(2);
    rows.forEach(row => {
        expect(row.id).toBe('');
        expect(getComputedStyle(row).display).toBe('table-row');
    });
    const downloads = rows[0].querySelectorAll('li');
    expect(downloads).toHaveLength(2);
    downloads.forEach(item => {
        expect(item.id).toBe('');
        expect(getComputedStyle(item).display).toBe('list-item');
    });
    expect(Array.from(downloads, item => item.textContent.trim())).toEqual(['Compass', 'Survex']);
    expect(downloads[0].querySelector('a').getAttribute('href')).toBe('/download/compass/');
    expect(rows[1].querySelectorAll('li')).toHaveLength(0);
    expect(document.getElementById('commit-template')).toBeNull();
    expect(document.getElementById('format-download-template')).toBeNull();
});

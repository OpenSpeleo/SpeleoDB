import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

const jquerySource = readFileSync(path.join(process.cwd(), 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };
beforeAll(() => { (0, eval)(jquerySource); });
beforeEach(() => {
    document.body.innerHTML = '<div id="modal_error"><span id="modal_error_txt"></span></div><div id="modal_success"><span id="modal_success_txt"></span></div>';
});
afterEach(() => {
    jqueryHost.jQuery(document).off();
    document.body.innerHTML = '';
});

import { attachGisViewForm } from './gis_view_form.ts';

function gisControls(): void {
    document.body.insertAdjacentHTML('beforeend', '<input name="csrfmiddlewaretoken" value="gis-csrf"><input id="name" value=" GIS "><input id="description" value=" Desc "><input type="checkbox" id="allow_precise_zoom" checked><button id="add_project_btn">Add</button><div id="projects_container"></div><div id="no_projects_message"></div><button id="btn_submit">Save</button>');
}
const gisOptions = { loadCommits: async () => [] };

it('loads projects immediately and serializes selected rows with trimmed form values', async () => {
    gisControls();
    const loadProjects = vi.fn(async () => [{ id: 'p1', name: '<Cave>' }]);
    const $ = jqueryHost.jQuery;
    const save = vi.fn(async (_payload: unknown) => ({}));
    const onSuccess = vi.fn();
    expect(attachGisViewForm({ ...gisOptions, loadProjects, save, onSuccess, reloadDelayMs: 0 })).toBeUndefined();
    expect(loadProjects).toHaveBeenCalledOnce();
    await Promise.resolve(); await Promise.resolve();
    $('#add_project_btn').trigger('click');
    expect(document.querySelector('.project-select option[value="p1"]')!.textContent).toBe('<Cave>');
    expect(document.querySelector('.project-select cave')).toBeNull();
    $('.project-select').val('p1').trigger('change');
    $('#btn_submit').trigger('click');
    expect(save.mock.calls[0]?.[0]).toEqual({ name: 'GIS', description: 'Desc', allow_precise_zoom: true, geographic_bound: null, projects: [{ project_id: 'p1', use_latest: true, commit_sha: '' }] });
    await vi.waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
});

it('rejects empty selection before submission without changing load-error settlement', async () => {
    gisControls();
    const loadProjects = async () => { throw new Error('Offline'); };
    const $ = jqueryHost.jQuery;
    const save = vi.fn(async () => ({}));
    expect(attachGisViewForm({ ...gisOptions, loadProjects, save })).toBeUndefined();
    await Promise.resolve(); await Promise.resolve();
    $('#btn_submit').trigger('click');
    expect(save).not.toHaveBeenCalled();
    expect($('#modal_error_txt').text()).toContain('at least one project');
});

it('shows the browser-local timestamp when choosing a specific revision', async () => {
    gisControls();
    const authoredDate = '2026-01-01T00:15:00Z';
    attachGisViewForm({
        loadProjects: async () => [{ id: 'p1', name: 'Cave' }],
        loadCommits: async () => [{ commit_sha: 'abcdef123456', commit_date: authoredDate, commit_author_name: 'Diver', commit_message: 'Survey' }],
        save: async () => ({}),
    });
    await Promise.resolve();
    const $ = jqueryHost.jQuery;
    $('#add_project_btn').trigger('click');
    $('.project-select').val('p1').trigger('change');
    $('.commit-mode-radio[value="specific"]').prop('checked', true).trigger('change');
    await vi.waitFor(() => expect(document.querySelector('.commit-sha-select option[value="abcdef123456"]')).not.toBeNull());
    const expectedDate = new Intl.DateTimeFormat(undefined, {
        year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    }).format(new Date(authoredDate));
    expect(document.querySelector('.commit-sha-select option[value="abcdef123456"]')!.textContent)
        .toBe(`[${expectedDate}] Diver: Survey - abcdef12`);
});

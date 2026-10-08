import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

const jquerySource = readFileSync(path.join(process.cwd(), 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };
let originalAjax: FormTestJQuery['ajax'];
beforeAll(() => { (0, eval)(jquerySource); });
beforeEach(() => {
    vi.useFakeTimers();
    originalAjax = jqueryHost.jQuery.ajax;
    document.body.innerHTML = '<div id="modal_error"><span id="modal_error_txt"></span></div><div id="modal_success"><span id="modal_success_txt"></span></div>';
});
afterEach(() => {
    jqueryHost.jQuery.ajax = originalAjax;
    jqueryHost.jQuery(document).off();
    document.body.innerHTML = '';
    vi.useRealTimers();
});

import { attachGisViewForm } from './gis_view_form.ts';

afterEach(() => { vi.unstubAllGlobals(); });
function gisControls(): void {
    document.body.insertAdjacentHTML('beforeend', '<input name="csrfmiddlewaretoken" value="gis-csrf"><input id="name" value=" GIS "><input id="description" value=" Desc "><input type="checkbox" id="allow_precise_zoom" checked><button id="add_project_btn">Add</button><div id="projects_container"></div><div id="no_projects_message"></div><button id="btn_submit">Save</button>');
}
const gisOptions = { endpoint: '/views/', projectsEndpoint: '/projects/', commitsEndpointBuilder: (id: string) => `/commits/${id}/` };

it('loads projects immediately and serializes selected rows with trimmed form values', async () => {
    gisControls();
    const fetcher = vi.fn(async () => ({ json: async () => [{ id: 'p1', name: '<Cave>' }] }));
    vi.stubGlobal('fetch', fetcher);
    const $ = jqueryHost.jQuery;
    $.ajax = vi.fn(() => ({}));
    expect(attachGisViewForm(gisOptions)).toBeUndefined();
    expect(fetcher).toHaveBeenCalledWith('/projects/', expect.objectContaining({ credentials: 'same-origin' }));
    await Promise.resolve(); await Promise.resolve();
    $('#add_project_btn').trigger('click');
    expect(document.querySelector('.project-select option[value="p1"]')!.textContent).toBe('<Cave>');
    expect(document.querySelector('.project-select cave')).toBeNull();
    $('.project-select').val('p1').trigger('change');
    $('#btn_submit').trigger('click');
    const request = $.ajax.mock.calls[0]![0];
    expect(JSON.parse(request.data!) as unknown).toEqual({ name: 'GIS', description: 'Desc', allow_precise_zoom: true, projects: [{ project_id: 'p1', use_latest: true, commit_sha: '' }] });
});

it('rejects empty selection before submission without changing load-error settlement', async () => {
    gisControls();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Offline')));
    const $ = jqueryHost.jQuery;
    $.ajax = vi.fn();
    expect(attachGisViewForm(gisOptions)).toBeUndefined();
    await Promise.resolve(); await Promise.resolve();
    $('#btn_submit').trigger('click');
    expect($.ajax).not.toHaveBeenCalled();
    expect($('#modal_error_txt').text()).toContain('at least one project');
});

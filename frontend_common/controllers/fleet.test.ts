import type { MockInstance } from 'vitest';
let ajax: MockInstance<JQueryStatic['ajax']>;
import type { FleetContext } from '../../ts-types/controllers/fleet.ts';
import type { ApplicationUrls } from '../../ts-types/browser/urls.d.ts';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initialize } from './fleet.ts';
import { attachFleetEntityCrud } from '../../frontend_private/static/private/ts/forms/fleet_entity_crud.ts';
import { attachFleetSettingsForm } from '../../frontend_private/static/private/ts/forms/fleet_settings_form.ts';
import { attachFleetWatchlist } from '../../frontend_private/static/private/ts/forms/fleet_watchlist.ts';
import { cylinderCollectPayload, sensorCollectPayload } from '../../frontend_private/static/private/ts/forms/fleet_modal_helpers.ts';
import { showAjaxErrorModal } from '../../frontend_private/static/private/ts/forms/ajax_errors.ts';
vi.mock('../../frontend_private/static/private/ts/forms/fleet_entity_crud.ts', () => ({ attachFleetEntityCrud: vi.fn() }));
vi.mock('../../frontend_private/static/private/ts/forms/fleet_settings_form.ts', () => ({ attachFleetSettingsForm: vi.fn() }));
vi.mock('../../frontend_private/static/private/ts/forms/fleet_watchlist.ts', () => ({ attachFleetWatchlist: vi.fn() }));
function init(context?: unknown) { return initialize(context as FleetContext); }
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    ajax = vi.spyOn($, 'ajax').mockImplementation(() => ({} as JQuery.jqXHR<unknown>));
    window.Urls = {} as ApplicationUrls;
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="csrf"><button class="toggle-sensor-btn" data-sensor-id="7"></button>';
});
afterEach(() => { $(document).off('click'); vi.restoreAllMocks(); delete (window as unknown as {Urls?: ApplicationUrls}).Urls; document.body.innerHTML = ''; });
it('waits for load and composes table, settings and entity helpers in order', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const pending = init({ kind: 'cylinder', mode: 'details', tableSelector: '#fleet', hasWrite: true, orderAscending: true, showDaysFilter: true, settingsEndpoint: '/settings/', settingsMessage: 'Saved', entityCrud: true });
    expect(attachFleetWatchlist).not.toHaveBeenCalled();
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    expect(vi.mocked(attachFleetWatchlist).mock.calls[0]![0]).toEqual({ tableSelector: '#fleet', dataTableOptions: { order: [[0, 'asc']], columnDefs: [{ targets: -1, orderable: false }] }, formSelector: '#watchlist_form', exportBtnSelector: '#btn_export_excel', exportUrlBuilder: undefined });
    expect(attachFleetSettingsForm).toHaveBeenCalledWith({ endpoint: '/settings/', successMessage: 'Saved' });
    expect(vi.mocked(attachFleetEntityCrud).mock.calls[0]![0]).toMatchObject({ entityLabel: 'cylinder', collectPayload: cylinderCollectPayload, addButtonSelector: '#add_cylinder_btn, #add_first_cylinder_btn', deleteModalSelector: '#delete_cylinder_modal' });
    expect(vi.mocked(attachFleetWatchlist).mock.invocationCallOrder[0]!).toBeLessThan(vi.mocked(attachFleetSettingsForm).mock.invocationCallOrder[0]!);
});
it('skips explicitly empty tables and keeps read-only table actions sortable', async () => {
    await init({ tableSelector: '#fleet', hasRows: false });
    expect(attachFleetWatchlist).not.toHaveBeenCalled();
    await init({ tableSelector: '#fleet', hasWrite: false });
    expect(vi.mocked(attachFleetWatchlist).mock.calls[0]![0].dataTableOptions).toEqual({});
    expect(attachFleetEntityCrud).not.toHaveBeenCalled();
});
it('uses sensor helpers for watchlists and resolves detail and export routes lazily', async () => {
    await init({ kind: 'sensor', mode: 'watchlist', entityCrud: true, tableSelector: '#fleet', detailRoute: 'api:v2:sensor-detail', exportRoute: 'api:v2:sensor-fleet-watchlist-export', fleetId: 3 });
    const options = vi.mocked(attachFleetEntityCrud).mock.calls[0]![0];
    expect(options.collectPayload).toBe(sensorCollectPayload);
    expect(options.deleteModalSelector).toBeUndefined();
    expect(options.addButtonSelector).toBeUndefined();
    expect(() => options.detailEndpoint!(7)).toThrow('Missing Django URL route: api:v2:sensor-detail');
    window.Urls['api:v2:sensor-detail'] = vi.fn().mockReturnValue('/sensor/7/');
    window.Urls['api:v2:sensor-fleet-watchlist-export'] = vi.fn().mockReturnValue('/fleet/export/');
    expect(options.detailEndpoint!(7)).toBe('/sensor/7/');
    expect(vi.mocked(attachFleetWatchlist).mock.calls[0]![0].exportUrlBuilder!('30')).toBe('/fleet/export/?days=30');
    expect(window.Urls['api:v2:sensor-fleet-watchlist-export']).toHaveBeenCalledWith(3);
});
it('delegates sensor clicks using the clicked receiver, PATCH and CSRF and repeats handlers', async () => {
    window.Urls['api:v2:sensor-toggle-functional'] = vi.fn(id => `/sensors/${id}/toggle/`);
    await init({ kind: 'sensor', mode: 'details' });
    await init({ kind: 'sensor', mode: 'details' });
    $('.toggle-sensor-btn').trigger('click');
    expect(ajax).toHaveBeenCalledTimes(2);
    expect(ajax.mock.calls[0]![0]).toMatchObject({ url: '/sensors/7/toggle/', method: 'PATCH', headers: { 'X-CSRFToken': 'csrf' }, error: showAjaxErrorModal });
});
it('rejects missing context and helper exceptions', async () => {
    await expect(init()).rejects.toThrow(TypeError);
    const error = new Error('Table failed');
    vi.mocked(attachFleetWatchlist).mockImplementationOnce(() => { throw error; });
    await expect(init({ tableSelector: '#fleet' })).rejects.toBe(error);
});

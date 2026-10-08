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

import { attachFleetWatchlist } from './fleet_watchlist.ts';

it('merges table overrides and preserves permissive nonnumeric days parsing', () => {
    document.body.insertAdjacentHTML('beforeend', '<table id="watch"></table><form id="filter"><input id="days"><button id="btn_update_watchlist">Update</button></form>');
    const table = vi.fn();
    const vendor = jqueryHost.jQuery as unknown as JQueryStatic;
    Object.assign(vendor.fn, { DataTable: table });
    attachFleetWatchlist({ tableSelector: '#watch', formSelector: '#filter', dataTableOptions: { paging: true } });
    expect(table).toHaveBeenCalledWith({ paging: true, searching: false, info: false, order: [] });
    jqueryHost.jQuery('#days').val('-1');
    expect(jqueryHost.jQuery('#filter').triggerHandler('submit')).toBe(false);
    jqueryHost.jQuery('#days').val('nonnumeric');
    expect(jqueryHost.jQuery('#filter').triggerHandler('submit')).toBe(true);
    expect(jqueryHost.jQuery('#btn_update_watchlist').prop('disabled')).toBe(true);
});

it('uses the export fallback only for a falsey input value', () => {
    document.body.insertAdjacentHTML('beforeend', '<input id="days"><button id="export">Export</button>');
    const originalLocation = window.location;
    const location = { href: '' };
    Object.defineProperty(window, 'location', { configurable: true, value: location });
    try {
        const builder = vi.fn((days: string) => `/export?days=${days}`);
        attachFleetWatchlist({ exportBtnSelector: '#export', exportUrlBuilder: builder });
        jqueryHost.jQuery('#export').trigger('click');
        expect(builder).toHaveBeenLastCalledWith('60');
        jqueryHost.jQuery('#days').val('0');
        jqueryHost.jQuery('#export').trigger('click');
        expect(builder).toHaveBeenLastCalledWith('0');
        expect(location.href).toBe('/export?days=0');
    } finally {
        Object.defineProperty(window, 'location', { configurable: true, value: originalLocation });
    }
});

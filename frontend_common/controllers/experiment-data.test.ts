import type { Mock } from 'vitest';
import type { ExperimentDataContext } from '../../ts-types/controllers/experiment-data.ts';
import type { AgGridApi, AgGridOptions, AgGridRuntime } from '../../ts-types/browser/ag-grid.d.ts';
import type { ExperimentTableFeature, ExperimentTableRow } from '../../ts-types/domain/experiment-table.ts';
let fetch: Mock<(url: string, options?: RequestInit) => Promise<{ok: boolean; status?: number; statusText?: string; json?(): Promise<unknown>}>>;
let createGrid: Mock<(element: HTMLElement, options: AgGridOptions<ExperimentTableRow>) => AgGridApi>;
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init } from './experiment-data.ts';
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
const context = { experimentId: 'experiment', dataUrl: '/data/', csrfToken: 'csrf' };
let api: {destroy: Mock<() => void>};
const fields = [{ id: 'status', name: 'Status', order: 0 }, { id: 'second', name: 'Second', order: 2 }, { id: 'first', name: 'First', order: 1 }];
function responses(features: ExperimentTableFeature[] = [{ properties: { project_name: 'Cave', first: 0, second: { value: 2 }, status: 'hidden' }, geometry: { coordinates: [0, 12] } }]) {
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ data: { experiment_fields: fields.map(field => ({ ...field })) } }) });
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ features }) });
}
async function flush() { for (let i = 0; i < 12; i++) await Promise.resolve(); }
beforeEach(() => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    vi.spyOn(console, 'error').mockImplementation(() => {});
    fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    vi.stubGlobal('alert', vi.fn());
    vi.stubGlobal('Urls', { 'api:v2:experiment-detail': vi.fn(() => '/experiment/'), 'api:v2:experiment-export-excel': vi.fn(() => '/export/') });
    api = { destroy: vi.fn() };
    createGrid = vi.fn(() => api);
    window.agGrid = { createGrid };
    document.body.innerHTML = '<div id="loadingSpinner"></div><div id="dataGridContainer"><div id="dataGrid"></div></div><div id="errorMessage"><span id="errorText"></span></div><span id="recordCount"></span><span id="columnCount"></span><button id="refreshDataBtn"></button><button id="exportExcelBtn">Export</button>';
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); delete (window as unknown as {agGrid?: AgGridRuntime}).agGrid; document.body.innerHTML = ''; });
it('waits for load but resolves initialization before initial fetching has completed', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    fetch.mockReturnValue(new Promise(() => {}));
    const pending = init(context);
    expect(fetch).not.toHaveBeenCalled();
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    expect(fetch).toHaveBeenCalledExactlyOnceWith('/experiment/', { credentials: 'same-origin' });
    expect($('#loadingSpinner').hasClass('hidden')).toBe(false);
});
it('loads details before rows, orders fields, excludes status and preserves zero-coordinate coercion', async () => {
    responses();
    await init(context);
    await flush();
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/experiment/', '/data/']);
    expect(createGrid).toHaveBeenCalledOnce();
    const options = createGrid.mock.calls[0]![1];
    expect(options.rowData).toEqual([{ 'Project Name': 'Cave', 'Project ID': '', 'Station ID': '', 'Station Name': '', Longitude: '', Latitude: 12, First: '0', Second: '{"value":2}' }]);
    expect(options.columnDefs.map(column => column.field)).toEqual(Object.keys(options.rowData[0]!));
    expect(options.paginationPageSize).toBe(50);
    expect($('#recordCount').text()).toBe('1');
    expect($('#columnCount').text()).toBe('8');
    expect($('#dataGridContainer').hasClass('hidden')).toBe(false);
});
it('currently hides the no-data error again after an empty successful load', async () => {
    responses([]);
    await init(context);
    await flush();
    expect(createGrid).not.toHaveBeenCalled();
    expect($('#errorText').text()).toBe('No data available to display');
    expect($('#errorMessage').hasClass('hidden')).toBe(true);
    expect($('#dataGridContainer').hasClass('hidden')).toBe(false);
});
it('renders request failures as text without rejecting init', async () => {
    fetch.mockResolvedValue({ ok: false, status: 403 });
    await expect(init(context)).resolves.toBeUndefined();
    await flush();
    expect($('#errorText').text()).toBe('Failed to fetch experiment details: 403');
    expect($('#errorMessage').hasClass('hidden')).toBe(false);
    expect(fetch).toHaveBeenCalledOnce();
});
it('destroys the existing grid before refresh and repeats initial requests on repeated init', async () => {
    responses();
    await init(context);
    await flush();
    responses();
    $('#refreshDataBtn').trigger('click');
    expect(api.destroy).toHaveBeenCalledOnce();
    await flush();
    responses();
    await init(context);
    await flush();
    expect(createGrid).toHaveBeenCalledTimes(3);
});
it('restores the clicked export button and alerts on export failure with exact request headers', async () => {
    responses();
    await init(context);
    await flush();
    fetch.mockResolvedValueOnce({ ok: false, status: 500, statusText: 'Failure' });
    $('#exportExcelBtn').trigger('click');
    expect($('#exportExcelBtn').prop('disabled')).toBe(true);
    await flush();
    expect(fetch).toHaveBeenLastCalledWith('/export/', { method: 'GET', headers: { 'X-CSRFToken': 'csrf' }, credentials: 'same-origin' });
    expect(alert).toHaveBeenCalledWith('Failed to export data: Export failed: 500 Failure');
    expect($('#exportExcelBtn').prop('disabled')).toBe(false);
    expect($('#exportExcelBtn').html()).toBe('Export');
});
it('rejects absent context and catches an unavailable grid vendor during data loading', async () => {
    await expect(init(undefined as unknown as ExperimentDataContext)).rejects.toThrow(TypeError);
    responses();
    delete (window as unknown as {agGrid?: AgGridRuntime}).agGrid;
    await init(context);
    await flush();
    expect($('#errorMessage').hasClass('hidden')).toBe(false);
    expect(console.error).toHaveBeenCalledWith('Error loading data:', expect.any(TypeError));
});

it('preserves callable and primitive coercion after the object serialization branch', async () => {
    const callable = () => 'field';
    responses([{ properties: { first: callable, second: Symbol('choice') }, geometry: { coordinates: [1, 2] } }]);
    await init(context);
    await flush();
    expect(createGrid.mock.calls[0]![1].rowData[0]).toMatchObject({ First: String(callable), Second: 'Symbol(choice)' });
});

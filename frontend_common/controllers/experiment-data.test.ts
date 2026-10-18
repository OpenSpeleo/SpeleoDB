import type { Mock } from 'vitest';
import type { AgGridApi, AgGridOptions, AgGridRuntime } from '../../ts-types/browser/ag-grid.d.ts';
import type { ExperimentTableRow } from '../../ts-types/domain/experiment-table.ts';
import { init } from './experiment-data.ts';
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

let createGrid: Mock<(element: HTMLElement, options: AgGridOptions<ExperimentTableRow>) => AgGridApi>;
let grid: { destroy: Mock<() => void> };
const context = { experimentId: 'experiment', gisToken: 'token' };
const fields = [{ id: 'status', name: 'Status', order: 0 }, { id: 'second', name: 'Second', order: 2 }, { id: 'first', name: 'First', order: 1 }];
const features = [{ properties: { project_name: 'Cave', first: 0, second: { value: 2 }, status: 'hidden' }, geometry: { type: 'Point', coordinates: [0, 12] } }];
beforeEach(() => {
    // AG Grid depends on browser layout; capture only its rendering boundary.
    grid = { destroy: vi.fn() }; createGrid = vi.fn(() => grid); window.agGrid = { createGrid };
    server.handle(request => ({ json: request.path === '/api/v2/experiments/experiment/' ? { experiment_fields: fields } : { type: 'FeatureCollection', features } }));
    document.body.innerHTML = '<div id="loadingSpinner"></div><div id="dataGridContainer"><div id="dataGrid"></div></div><div id="errorMessage"><span id="errorText"></span></div><span id="recordCount"></span><span id="columnCount"></span><button id="refreshDataBtn"></button><button id="exportExcelBtn">Export</button>';
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); delete (window as unknown as { agGrid?: AgGridRuntime }).agGrid; document.body.innerHTML = ''; });

it('loads generated experiment details before GeoJSON and preserves field order and status filtering', async () => {
    await init(context); await vi.waitFor(() => expect(createGrid).toHaveBeenCalledOnce());
    expect(server.requests.map(request => request.path)).toEqual(['/api/v2/experiments/experiment/', '/api/v2/gis-ogc/experiment/token']);
    const options = createGrid.mock.calls[0]![1];
    expect(options.rowData).toEqual([{ 'Project Name': 'Cave', 'Project ID': '', 'Station ID': '', 'Station Name': '', Longitude: '', Latitude: 12, First: '0', Second: '{"value":2}' }]);
    expect(options.columnDefs.map(column => column.field)).toEqual(Object.keys(options.rowData[0]!));
    expect(options.paginationPageSize).toBe(50); expect($('#recordCount').text()).toBe('1');
    expect($('#dataGridContainer').hasClass('hidden')).toBe(false);
});

it('renders HTTP errors as text and avoids loading GeoJSON after rejected details', async () => {
    server.reply({ status: 403, json: { detail: '<Denied>' } });
    await init(context); await vi.waitFor(() => expect($('#errorText').text()).toBe('<Denied>'));
    expect($('#errorText denied')).toHaveLength(0); expect(server.requests).toHaveLength(1);
    expect(createGrid).not.toHaveBeenCalled();
});

it('destroys the current grid before refreshing both generated operations', async () => {
    await init(context); await vi.waitFor(() => expect(createGrid).toHaveBeenCalledOnce());
    $('#refreshDataBtn').trigger('click'); expect(grid.destroy).toHaveBeenCalledOnce();
    await vi.waitFor(() => expect(createGrid).toHaveBeenCalledTimes(2));
    expect(server.requests).toHaveLength(4);
});

it('restores the clicked export button on an HTTP failure', async () => {
    // Native alert cannot be implemented by JSDOM; request and failure handling remain real.
    vi.stubGlobal('alert', vi.fn());
    await init(context); await vi.waitFor(() => expect(createGrid).toHaveBeenCalledOnce());
    server.reply({ status: 500, json: { detail: 'Export failed' } });
    $('#exportExcelBtn').trigger('click'); expect($('#exportExcelBtn').prop('disabled')).toBe(true);
    await vi.waitFor(() => expect(alert).toHaveBeenCalledWith('Failed to export data: Export failed'));
    expect(server.requests.at(-1)!.path).toBe('/api/v2/experiments/experiment/export/excel/');
    expect($('#exportExcelBtn').prop('disabled')).toBe(false); expect($('#exportExcelBtn').text()).toBe('Export');
});

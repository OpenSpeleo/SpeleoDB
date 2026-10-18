import type { GISListRecord, GISUploadErrorDetails } from '../../ts-types/controllers/gis-lists.ts';
import type { ApplicationUrls } from '../../ts-types/browser/urls.d.ts';
import { buildGISGeometryListMarkup } from './gis-geometries.ts';

beforeEach(() => {
    globalThis.Urls = { 'private:gis_geometry_details': id => `/private/gis-geometry/${id}/` } as ApplicationUrls;
});
afterEach(() => { Reflect.deleteProperty(globalThis, 'Urls'); });

describe('GIS Geometries management listing', () => {
    it('reuses table/card Open controls and access pills without source fields or uploads', () => {
        const markup = buildGISGeometryListMarkup([{
            id: 'geometry-id', name: 'Survey boundary', color: '#123456',
            created_by: 'creator@example.com', user_permission_level_label: 'READ_AND_WRITE',
            creation_date: '2026-09-16T10:00:00Z',
        }], '/static/private/media/right_arrow.svg');
        document.body.innerHTML = `<table><tbody>${markup.tableHtml}</tbody></table>${markup.cardsHtml}`;
        expect(document.querySelectorAll('a[href="/private/gis-geometry/geometry-id/"]')).toHaveLength(2);
        expect(document.querySelectorAll('img[src$="right_arrow.svg"]')).toHaveLength(2);
        expect(document.querySelectorAll('.bg-pastel-navy')).toHaveLength(2);
        expect(document.querySelectorAll('tbody td')).toHaveLength(6);
        expect(document.body.textContent).not.toMatch(/Source|Download|Upload/);
    });

    it('escapes stored text and sanitizes color and action URLs in both layouts', () => {
        globalThis.Urls['private:gis_geometry_details'] = () => 'javascript:alert(1)';
        const markup = buildGISGeometryListMarkup([{
            id: 'bad" onmouseover="alert(1)', name: '<img src=x onerror=alert(1)>',
            created_by: '<svg onload=alert(1)>', color: 'red;background:url(evil)',
        }]);
        document.body.innerHTML = `<table><tbody>${markup.tableHtml}</tbody></table>${markup.cardsHtml}`;
        expect(document.querySelector<HTMLElement>('script,[onerror],[onload],[onmouseover]')!).toBeNull();
        expect(document.querySelectorAll('a[href^="javascript:"]')).toHaveLength(0);
        expect(document.body.textContent).toContain('<img src=x onerror=alert(1)>');
        expect(document.querySelector<HTMLElement>('.w-3.h-3')!.style.backgroundColor).toBe('rgb(148, 163, 184)');
    });

    it('offers a geometry-specific empty state', () => {
        const markup = buildGISGeometryListMarkup([]);
        expect(markup.tableHtml).toContain('colspan="6"');
        expect(markup.cardsHtml).toContain('No GIS Geometries yet');
        expect(markup.cardsHtml).toContain('Create a line or polygon');
        expect(markup.cardsHtml).not.toContain('Upload');
    });
});

import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });
import { init } from './gis-geometries.ts';

it('loads and reloads generated geometry metadata into both responsive lists', async () => {
    document.body.innerHTML = '<table><tbody id="gis-geometries-table-body"></tbody></table><div id="gis-geometries-cards-container"></div>';
    server.reply({ json: [{ id: 'geometry', name: 'Boundary' }] });
    const api = init({ openIconUrl: '/open.svg' });
    await vi.waitFor(() => expect(document.querySelectorAll('img[src="/open.svg"]')).toHaveLength(2));
    expect(server.requests[0]!.path).toBe('/api/v2/gis-geometries/');
    server.reply({ json: [] }); api.reload();
    await vi.waitFor(() => expect(document.body.textContent).toContain('No GIS Geometries yet'));
    expect(server.requests).toHaveLength(2);
});

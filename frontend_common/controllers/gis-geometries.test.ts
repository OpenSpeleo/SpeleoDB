import type { Mock } from 'vitest';
import type { ApplicationUrls } from '../../ts-types/browser/urls.d.ts';
import type { GISListRecord, GISListContext, GISUploadListContext, GISUploadErrorDetails } from '../../ts-types/controllers/gis-lists.ts';
import type { TaggedListApi, TaggedListOptions } from '../../ts-types/domain/forms/tagged-list.ts';
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

vi.mock('../../frontend_private/static/private/ts/forms/tagged_entity_list.ts', () => ({ attachTaggedEntityList: vi.fn() }));
import { init as initialize } from './gis-geometries.ts';
import { attachTaggedEntityList } from '../../frontend_private/static/private/ts/forms/tagged_entity_list.ts';

describe('GIS Geometries initialization', () => {
    beforeEach(() => {
        attachment.mockReset();
        document.body.innerHTML = '<table><tbody id="gis-geometries-table-body"></tbody></table><div id="gis-geometries-cards-container"></div>';
    });
    it('immediately forwards context, returns the original facade and renders both targets', () => {
        const api = { reload() {}, openEditModal() {}, openDeleteModal() {} };
        attachment.mockReturnValue(api);
        expect(init({ listEndpoint: '/geometries/', openIconUrl: '/open.svg' })).toBe(api);
        const options = attachment.mock.calls[0]![0];
        expect(options).toMatchObject({ listEndpoint: '/geometries/', entityLabel: 'GIS Geometry', loadFailedMessage: 'Unable to load GIS Geometries. Refresh the page to try again.' });
        options.renderList!([{ id: 1, name: 'Boundary' }], {} as TaggedListApi);
        expect(document.querySelectorAll('img[src="/open.svg"]')).toHaveLength(2);
        expect(document.getElementById('gis-geometries-table-body')!.textContent).toContain('Boundary');
        expect(document.getElementById('gis-geometries-cards-container')!.textContent).toContain('Boundary');
    });
    it('attaches on every call and preserves missing context, target and helper failures', () => {
        init({}); init({});
        expect(attachTaggedEntityList).toHaveBeenCalledTimes(2);
        expect(() => init()).toThrow(TypeError);
        document.body.innerHTML = '';
        expect(() => attachment.mock.calls[0]![0].renderList!([], {} as TaggedListApi)).toThrow(TypeError);
        const error = new Error('list failed');
        attachment.mockImplementationOnce(() => { throw error; });
        expect(() => init({})).toThrow(error);
    });
});

function init(context?: unknown) { return initialize(context as GISListContext); }
const attachment = vi.mocked(attachTaggedEntityList) as unknown as Mock<(options: TaggedListOptions<GISListRecord>) => TaggedListApi>;

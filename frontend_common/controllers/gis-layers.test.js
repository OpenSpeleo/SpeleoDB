import { buildGISLayerListMarkup } from './gis-layers.js';

function layer(overrides = {}) {
    return {
        id: '11111111-1111-4111-8111-111111111111', name: 'Protected Areas',
        description: 'Boundaries', color: '#377eb8', created_by: 'creator@example.com',
        user_permission_level_label: 'READ_ONLY', can_write: false, can_delete: false,
        source_format: 'KMZ', modified_date: '2026-08-29T12:00:00Z', ...overrides,
    };
}

beforeEach(() => {
    globalThis.Urls = {
        'api:v2:gis-layer-source': id => `/api/v2/gis-layers/${id}/source/`,
        'private:gis_layer_details': id => `/private/gis-layer/${id}/`,
    };
});
afterEach(() => { delete globalThis.Urls; });

describe('GIS Layer management markup', () => {
    it('shows source download and the standard Open control', () => {
        const { tableHtml, cardsHtml } = buildGISLayerListMarkup(
            [layer()],
            '/static/private/media/right_arrow.svg',
        );
        document.body.innerHTML = `<table><tbody>${tableHtml}</tbody></table>${cardsHtml}`;
        expect(document.body.textContent).toContain('Protected Areas');
        expect(document.body.textContent).toContain('KMZ');
        expect(document.querySelectorAll('a[href$="/source/"]')).toHaveLength(2);
        expect(document.querySelectorAll('a[href$="111111111111/"]')).toHaveLength(2);
        expect(document.querySelectorAll('img[src$="right_arrow.svg"]')).toHaveLength(2);
        expect(document.querySelectorAll('.btn-edit-gis-layer')).toHaveLength(0);
        expect(document.querySelectorAll('.btn-delete-gis-layer')).toHaveLength(0);
        expect(document.querySelector('.bg-pastel-beige')).not.toBeNull();
    });

    it('does not expose inline mutations for writers or administrators', () => {
        const { tableHtml } = buildGISLayerListMarkup([layer({
            can_write: true,
            can_delete: true,
        })], '/static/private/media/right_arrow.svg');
        document.body.innerHTML = `<table><tbody>${tableHtml}</tbody></table>`;
        expect(document.querySelector('.btn-edit-gis-layer')).toBeNull();
        expect(document.querySelector('.btn-delete-gis-layer')).toBeNull();
    });

    it('escapes names, descriptions, creators, IDs, and validates colors', () => {
        const { tableHtml } = buildGISLayerListMarkup([layer({
            id: 'bad\" onmouseover=\"alert(1)', name: '<img src=x onerror=alert(1)>',
            description: '<script>alert(1)</script>',
            created_by: '<svg/onload=alert(1)>', color: 'red;background:url(evil)', can_write: true,
        })]);
        document.body.innerHTML = `<table><tbody>${tableHtml}</tbody></table>`;
        expect(document.querySelector('script,[onmouseover],[onload]')).toBeNull();
        expect(document.querySelectorAll('img')).toHaveLength(1);
        expect(document.querySelector('svg')).not.toBeNull();
        expect(document.body.textContent).toContain('<img src=x onerror=alert(1)>');
        expect(document.querySelector('.w-3.h-3').style.backgroundColor).toBe('rgb(148, 163, 184)');
    });

    it('sanitizes action URLs while retaining trusted static icons', () => {
        globalThis.Urls['api:v2:gis-layer-source'] = () => 'javascript:alert(1)';
        globalThis.Urls['private:gis_layer_details'] = () => 'data:text/html,<script>alert(1)</script>';
        const { tableHtml } = buildGISLayerListMarkup([layer()]);
        document.body.innerHTML = `<table><tbody>${tableHtml}</tbody></table>`;
        expect([...document.querySelectorAll('a')].every(anchor => !/^(javascript|data):/i.test(anchor.getAttribute('href')))).toBe(true);
        expect(document.querySelectorAll('svg')).not.toHaveLength(0);
    });

    it('renders source format and an empty state', () => {
        const emptyMarkup = buildGISLayerListMarkup([]);
        expect(emptyMarkup.tableHtml).toContain('No GIS Layers yet');
        expect(emptyMarkup.cardsHtml).toContain('No GIS Layers yet');
        const { tableHtml, cardsHtml } = buildGISLayerListMarkup([
            layer({ source_format: 'GEOJSON' }),
        ]);
        document.body.innerHTML = `<table><tbody>${tableHtml}</tbody></table>${cardsHtml}`;
        expect(document.body.textContent).toContain('GEOJSON');
        expect(document.body.textContent).not.toContain('features');
    });
});

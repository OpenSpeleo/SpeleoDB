import type { GISListRecord, GISListContext } from '../../ts-types/controllers/gis-lists.ts';
import { attachTaggedEntityList } from '../../frontend_private/static/private/ts/forms/tagged_entity_list.ts';
import { buildGISGeometryListMarkup } from '../presentation/gis-overlays.ts';

export { buildGISGeometryListMarkup } from '../presentation/gis-overlays.ts';

export function init(context: GISListContext) {
    return attachTaggedEntityList<GISListRecord>({
        listEndpoint: context.listEndpoint,
        entityLabel: 'GIS Geometry',
        loadFailedMessage: 'Unable to load GIS Geometries. Refresh the page to try again.',
        renderList(geometries) {
            const { tableHtml, cardsHtml } = buildGISGeometryListMarkup(geometries, context.openIconUrl);
            (document.getElementById('gis-geometries-table-body') as HTMLElement).innerHTML = tableHtml;
            (document.getElementById('gis-geometries-cards-container') as HTMLElement).innerHTML = cardsHtml;
        },
    });
}

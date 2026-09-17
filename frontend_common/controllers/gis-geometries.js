import { attachTaggedEntityList } from '../../frontend_private/static/private/js/forms/tagged_entity_list.js';
import { buildGISOverlayListMarkup } from './gis-layers.js';

export function buildGISGeometryListMarkup(geometries, openIconUrl = '') {
    return buildGISOverlayListMarkup(geometries, openIconUrl, {
        entityLabel: 'GIS Geometry',
        pluralLabel: 'GIS Geometry',
        detailsRoute: 'private:gis_geometry_details',
        showSource: false,
        emptyHint: 'Create a line or polygon on the survey map to get started.',
    });
}

export function init(context) {
    return attachTaggedEntityList({
        listEndpoint: context.listEndpoint,
        entityLabel: 'GIS Geometry',
        loadFailedMessage: 'Unable to load GIS Geometry. Refresh the page to try again.',
        renderList(geometries) {
            const { tableHtml, cardsHtml } = buildGISGeometryListMarkup(geometries, context.openIconUrl);
            document.getElementById('gis-geometries-table-body').innerHTML = tableHtml;
            document.getElementById('gis-geometries-cards-container').innerHTML = cardsHtml;
        },
    });
}

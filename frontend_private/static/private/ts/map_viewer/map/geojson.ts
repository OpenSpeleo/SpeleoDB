import { createCoordinateBounds, decodeGeoJSONBBox } from '@speleodb/map-core/coordinate-bounds';
import { geometryPositionSteps } from '@speleodb/map-core/preparation';
import { Renderer } from './renderer.ts';
import type { Geometry } from 'geojson';
import type { ViewerGeoJSON } from '../../../../../../ts-types/domain/map-geometry.ts';

export function computeGeoJSONBounds(geojsonData: ViewerGeoJSON | null | undefined, { wrapLongitude = true } = {}) {
    const bounds = new Renderer.LngLatBounds();
    const coordinates = createCoordinateBounds({ bbox: decodeGeoJSONBBox(geojsonData?.bbox), wrapLongitude });
    const extendGeometry = (geometry: Geometry | null | undefined): void => {
        for (const position of geometryPositionSteps(geometry)) {
            // Existing finiteness checks own invalid-coordinate handling.
            if (position) coordinates.extend(position);
        }
    };
    if (coordinates.bbox) {
        for (const corner of coordinates.bbox) bounds.extend(corner);
        return bounds;
    }

    if (geojsonData?.type === 'FeatureCollection') {
        geojsonData.features?.forEach(feature => extendGeometry(feature.geometry));
    } else if (geojsonData?.type === 'Feature') {
        extendGeometry(geojsonData.geometry);
    } else {
        extendGeometry(geojsonData);
    }

    const corners = coordinates.finish();
    if (corners) for (const corner of corners) bounds.extend(corner);
    return bounds;
}

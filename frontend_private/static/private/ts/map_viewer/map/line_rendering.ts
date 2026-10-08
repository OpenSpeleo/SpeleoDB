import { createGeoJSONLineWidth } from '@speleodb/map-viewer';
import type { ZoomInterpolation } from '../../../../../../ts-types/domain/map-geometry.ts';

/** Thin shared overview strokes with each renderer's existing detail widths. */
export function geoJSONLineWidth(detailWidth: number, closeWidth = detailWidth, overviewWidthOffset = 0): ZoomInterpolation {
    return createGeoJSONLineWidth(detailWidth, closeWidth, overviewWidthOffset) as ZoomInterpolation;
}

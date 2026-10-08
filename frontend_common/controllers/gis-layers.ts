import type { GISUploadListContext } from '../../ts-types/controllers/gis-lists.ts';
import { attachGISLayerList } from '../features/gis-layers.ts';

export { buildGISOverlayListMarkup, buildGISLayerListMarkup } from '../presentation/gis-overlays.ts';
export { renderGISLayerUploadError } from '../features/gis-layers.ts';

export function init(context: GISUploadListContext) {
    return attachGISLayerList(context);
}

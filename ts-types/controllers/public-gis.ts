import type { MapRuntimeContext } from '../domain/map-runtime.ts';
export type PublicGISContext = Pick<MapRuntimeContext,
    'csrfToken' | 'mapboxToken' | 'viewMode' | 'gisToken' | 'allowPreciseZoom'>;

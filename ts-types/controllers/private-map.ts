import type { MapRuntimeContext, MapRuntimeIcons } from '../domain/map-runtime.ts';
export interface PrivateMapContext extends Omit<MapRuntimeContext, 'icons' | 'csrfToken'> {
    csrfToken: string;
    icons?: MapRuntimeIcons;
}

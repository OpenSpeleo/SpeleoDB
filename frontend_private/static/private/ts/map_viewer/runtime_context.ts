import { MAP_ICON_URLS } from '@speleodb/map-viewer/icons';
import type { MapRuntimeContext, MapRuntimeIcons } from '../../../../../ts-types/domain/map-runtime.ts';

// Adapt the shared asset catalog to the existing Django/UI context keys once,
// so map sprites, menus and dialogs all receive the same complete icon set.
const sharedIcons = Object.freeze({
    sensor: MAP_ICON_URLS.sensor,
    biology: MAP_ICON_URLS.biology,
    bone: MAP_ICON_URLS.bones,
    artifact: MAP_ICON_URLS.artifact,
    geology: MAP_ICON_URLS.geology,
    explorationLead: MAP_ICON_URLS.explorationLead,
    cylinderOrange: MAP_ICON_URLS.cylinder,
});
type ResolvedContext = Readonly<MapRuntimeContext & { icons: Readonly<Required<MapRuntimeIcons>> }>;

let runtimeContext: ResolvedContext = Object.freeze({ icons: sharedIcons });

export function configureRuntimeContext(context: unknown): ResolvedContext {
    // Django owns the context shape; retain shallow normalization of its other
    // properties while resolving optional icon overrides against shared assets.
    const normalized = (context && typeof context === 'object' ? context : {}) as Partial<MapRuntimeContext>;
    const icons = { ...sharedIcons };
    for (const key of Object.keys(sharedIcons) as (keyof MapRuntimeIcons)[]) {
        const override = normalized.icons?.[key];
        if (typeof override === 'string' && override.trim()) icons[key] = override;
    }
    runtimeContext = Object.freeze({
        ...normalized,
        icons: Object.freeze(icons),
    });
    return runtimeContext;
}

export function getRuntimeContext(): ResolvedContext {
    return runtimeContext;
}

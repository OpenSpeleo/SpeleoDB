import type { MapRuntimeContext } from '../../../../../ts-types/domain/map-runtime.ts';

let runtimeContext: Readonly<MapRuntimeContext> = Object.freeze({ icons: Object.freeze({}) });

export function configureRuntimeContext(context: unknown): Readonly<MapRuntimeContext> {
    // Django owns the context shape; retain the existing shallow normalization
    // without validating or rejecting previously accepted object properties.
    const normalized = (context && typeof context === 'object' ? context : {}) as Partial<MapRuntimeContext>;
    runtimeContext = Object.freeze({
        ...normalized,
        icons: Object.freeze({ ...(normalized.icons || {}) }),
    });
    return runtimeContext;
}

export function getRuntimeContext(): Readonly<MapRuntimeContext> {
    return runtimeContext;
}

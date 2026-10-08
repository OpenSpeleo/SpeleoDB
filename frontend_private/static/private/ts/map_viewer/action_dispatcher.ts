import type { MapActionRegistry } from '../../../../../ts-types/domain/map-actions.ts';
let actionRegistry: Readonly<Partial<MapActionRegistry>> = Object.freeze({});
let initialized = false;

function invokeAction(element: HTMLElement) {
    const actionName = element.dataset.mapAction;
    const separator = actionName?.indexOf('.');
    if (!actionName || separator! < 1) return;
    const namespace = actionName.slice(0, separator);
    const method = actionName.slice(separator! + 1);
    const owner = actionRegistry[namespace as keyof MapActionRegistry];
    const action = owner?.[method as keyof typeof owner];
    if (typeof action !== 'function') {
        throw new Error(`Unknown map action: ${actionName}`);
    }
    const args: unknown = element.dataset.mapArgs ? JSON.parse(element.dataset.mapArgs) : [];
    // Inert DOM arguments retain the original unchecked apply contract.
    (action as (this: unknown, ...args: unknown[]) => unknown).apply(owner, args as unknown[]);
}

export function initMapActionDispatcher(registry: MapActionRegistry) {
    actionRegistry = Object.freeze({ ...registry });
    if (initialized) return;
    initialized = true;
    document.addEventListener('click', event => {
        const element = (event.target as Element).closest<HTMLElement>('[data-map-action]:not([data-map-event="change"])');
        if (element) invokeAction(element);
    });
    document.addEventListener('change', event => {
        const element = (event.target as Element).closest<HTMLElement>('[data-map-action][data-map-event="change"]');
        if (element) invokeAction(element);
    });
}

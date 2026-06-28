let actionRegistry = Object.freeze({});
let initialized = false;

function invokeAction(element) {
    const actionName = element.dataset.mapAction;
    const separator = actionName?.indexOf('.');
    if (!actionName || separator < 1) return;
    const namespace = actionName.slice(0, separator);
    const method = actionName.slice(separator + 1);
    const owner = actionRegistry[namespace];
    const action = owner?.[method];
    if (typeof action !== 'function') {
        throw new Error(`Unknown map action: ${actionName}`);
    }
    const args = element.dataset.mapArgs ? JSON.parse(element.dataset.mapArgs) : [];
    action.apply(owner, args);
}

export function initMapActionDispatcher(registry) {
    actionRegistry = Object.freeze({ ...registry });
    if (initialized) return;
    initialized = true;
    document.addEventListener('click', event => {
        const element = event.target.closest('[data-map-action]:not([data-map-event="change"])');
        if (element) invokeAction(element);
    });
    document.addEventListener('change', event => {
        const element = event.target.closest('[data-map-action][data-map-event="change"]');
        if (element) invokeAction(element);
    });
}

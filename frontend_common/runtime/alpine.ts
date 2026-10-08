import type { AlpineBindings, AlpineBinding, AlpineRuntime } from '../../ts-types/browser/alpine.d.ts';

interface BindingSession {
    bindings: Map<string, AlpineBinding>;
    scopes: WeakSet<Element>;
    installed: boolean;
    queued: boolean;
}
const sessions = new WeakMap<Document, BindingSession>();
const SCOPE = '[data-speleodb-scope]';

/** Use the vendor's own tree lifecycle so cloned menus retain asynchronous initialization. */
export function registerAlpineBindings(bindings: AlpineBindings, host: Window = window): void {
    const document = host.document;
    let session = sessions.get(document);
    if (!session) {
        session = { bindings: new Map(), scopes: new WeakSet(), installed: false, queued: false };
        sessions.set(document, session);
    }
    for (const [name, binding] of Object.entries(bindings)) session.bindings.set(name, binding);
    const current = session;
    const initialize = (alpine: AlpineRuntime): void => {
        if (!current.installed) {
            current.installed = true;
            alpine.addRootSelector(() => SCOPE);
            alpine.interceptInit(element => {
                const name = element.getAttribute('data-speleodb-bind');
                const binding = name ? current.bindings.get(name) : undefined;
                if (binding) {
                    alpine.bind(element, binding);
                    if (element.matches(SCOPE)) current.scopes.add(element);
                }
            });
        }
        for (const scope of document.querySelectorAll(SCOPE)) {
            const name = scope.getAttribute('data-speleodb-bind');
            if (!name || !current.bindings.has(name) || current.scopes.has(scope)) continue;
            // An unregistered ancestor owns the scope chain; wait for its controller.
            let parent = scope.parentElement?.closest(SCOPE);
            let waiting = false;
            while (parent) {
                if (!current.scopes.has(parent)) { waiting = true; break; }
                parent = parent.parentElement?.closest(SCOPE);
            }
            if (!waiting) alpine.initTree(scope);
        }
    };
    if (current.queued) return;
    current.queued = true;
    const ready = (): void => {
        current.queued = false;
        if (host.Alpine) initialize(host.Alpine);
    };
    // The CDN queues auto-start before this microtask. Never invoke start twice.
    if (host.Alpine) host.queueMicrotask(ready);
    else document.addEventListener('alpine:initialized', ready, { once: true });
}

export function afterWindowLoad(): Promise<Event | void> {
    if (document.readyState === 'complete') return Promise.resolve();
    return new Promise<Event>(resolve => window.addEventListener('load', resolve, { once: true }));
}

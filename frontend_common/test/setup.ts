vi.mock('../../frontend_private/static/private/ts/map_viewer/map/renderer.ts', () => ({
    get Renderer() { return globalThis.__mapRenderer; },
}));

function createMemoryStorage() {
    const values = new Map<string, string>();
    return {
        clear: () => values.clear(),
        getItem: (key: string) => values.has(String(key)) ? values.get(String(key)) : null,
        key: (index: number) => Array.from(values.keys())[index] ?? null,
        removeItem: (key: string) => values.delete(String(key)),
        setItem: (key: string, value: string) => values.set(String(key), String(value)),
        get length() { return values.size; },
    };
}

if (typeof window !== 'undefined') {
    for (const storageName of ['localStorage', 'sessionStorage']) {
        const storage = createMemoryStorage();
        Object.defineProperty(globalThis, storageName, {
            configurable: true,
            value: storage,
        });
        Object.defineProperty(window, storageName, {
            configurable: true,
            value: storage,
        });
    }
}

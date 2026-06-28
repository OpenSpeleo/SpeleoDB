function createMemoryStorage() {
    const values = new Map();
    return {
        clear: () => values.clear(),
        getItem: key => values.has(String(key)) ? values.get(String(key)) : null,
        key: index => Array.from(values.keys())[index] ?? null,
        removeItem: key => values.delete(String(key)),
        setItem: (key, value) => values.set(String(key), String(value)),
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

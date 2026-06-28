let runtimeContext = Object.freeze({ icons: Object.freeze({}) });

export function configureRuntimeContext(context) {
    const normalized = context && typeof context === 'object' ? context : {};
    runtimeContext = Object.freeze({
        ...normalized,
        icons: Object.freeze({ ...(normalized.icons || {}) }),
    });
    return runtimeContext;
}

export function getRuntimeContext() {
    return runtimeContext;
}

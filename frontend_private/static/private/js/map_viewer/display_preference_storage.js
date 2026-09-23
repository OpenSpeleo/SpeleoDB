// Display preferences are intent in memory; storage never gates a control paint.
const pendingWrites = new Map();
let frame = null;
let timer = null;

function cancelFlush() {
    if (frame !== null) cancelAnimationFrame(frame);
    if (timer !== null) clearTimeout(timer);
    frame = null;
    timer = null;
}

export function flushPreferenceWrites(key) {
    const entries = key === undefined ? [...pendingWrites] : pendingWrites.has(key) ? [[key, pendingWrites.get(key)]] : [];
    for (const [storageKey, { readValue, onResult }] of entries) {
        pendingWrites.delete(storageKey);
        try {
            localStorage.setItem(storageKey, JSON.stringify(readValue()));
            onResult?.(null);
        } catch (error) {
            onResult?.(error);
        }
    }
    if (!pendingWrites.size) cancelFlush();
}

/** Coalesce by key, reading the latest in-memory value only when writing. */
export function schedulePreferenceWrite(key, readValue, onResult) {
    pendingWrites.set(key, { readValue, onResult });
    if (frame !== null || timer !== null) return;
    const queueTask = () => {
        frame = null;
        timer = setTimeout(() => {
            timer = null;
            flushPreferenceWrites();
        }, 0);
    };
    if (typeof requestAnimationFrame === 'function' && document.visibilityState !== 'hidden') {
        frame = requestAnimationFrame(queueTask);
    } else {
        queueTask();
    }
}

window.addEventListener('pagehide', () => flushPreferenceWrites());

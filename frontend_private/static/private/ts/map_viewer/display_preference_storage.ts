// Display preferences are intent in memory; storage never gates a control paint.
interface PendingWrite {
    readValue: () => unknown;
    onResult: ((error: unknown) => void) | undefined;
}

const pendingWrites = new Map<string, PendingWrite>();
let frame: number | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;

function cancelFlush() {
    if (frame !== null) cancelAnimationFrame(frame);
    if (timer !== null) clearTimeout(timer);
    frame = null;
    timer = null;
}

export function flushPreferenceWrites(key?: string) {
    const entries: [string, PendingWrite][] = key === undefined ? [...pendingWrites] : pendingWrites.has(key) ? [[key, pendingWrites.get(key) as PendingWrite]] : [];
    for (const [storageKey, { readValue, onResult }] of entries) {
        pendingWrites.delete(storageKey);
        try {
            // Storage performs its existing string coercion even when stringify
            // returns undefined; do not add a fallback or validation here.
            localStorage.setItem(storageKey, JSON.stringify(readValue()));
            onResult?.(null);
        } catch (error) {
            onResult?.(error);
        }
    }
    if (!pendingWrites.size) cancelFlush();
}

/** Coalesce by key, reading the latest in-memory value only when writing. */
export function schedulePreferenceWrite(key: string, readValue: () => unknown, onResult?: (error: unknown) => void) {
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

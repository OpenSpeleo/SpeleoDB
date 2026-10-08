const POLL_INTERVAL_MS = 1000;
const ATTEMPT_KEY = 'speleo_dev_reload_target';
const GENERATION = /^[a-zA-Z0-9-]+\/[0-9]+$/;

/** Poll completed publication only; storage records the target before navigation. */
export function startDevelopmentReload(script = document.querySelector<HTMLScriptElement>('script[data-speleodb-generation]')) {
    const rendered = script?.dataset.speleodbGeneration;
    const endpoint = script?.dataset.speleodbReload;
    if (!rendered || !GENERATION.test(rendered) || !endpoint) return () => {};
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const stop = () => { stopped = true; clearTimeout(timer); };
    async function poll() {
        try {
            const response = await fetch(endpoint!, { cache: 'no-store', credentials: 'same-origin' });
            if (!response.ok) throw new Error('Development generation unavailable');
            const data: unknown = await response.json();
            const target = data && typeof data === 'object' && 'generation' in data ? data.generation : null;
            if (!stopped && typeof target === 'string' && GENERATION.test(target) && target !== rendered) {
                // Without persistent per-tab storage, stale HTML could reload forever.
                if (sessionStorage.getItem(ATTEMPT_KEY) !== target) {
                    sessionStorage.setItem(ATTEMPT_KEY, target);
                    stop();
                    window.location.reload();
                }
            }
        } catch {
            // A failed build, offline server or unavailable storage must not navigate.
        } finally {
            if (!stopped) timer = setTimeout(() => { void poll(); }, POLL_INTERVAL_MS);
        }
    }
    void poll();
    return stop;
}

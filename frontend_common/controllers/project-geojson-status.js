const POLL_INTERVAL_MS = 5000;
const RETRY_INTERVAL_MS = 30_000;
const REQUEST_TIMEOUT_MS = 30_000;
const ACTIVE_STATES = new Set(['pending', 'queued', 'running']);
const STATE_MESSAGES = {
    pending: 'Upload saved; map generation pending.',
    queued: 'Upload saved; map generation pending.',
    running: 'Upload saved; generating the map.',
    ready: 'Map ready.',
    failed: 'Upload saved; map generation failed.',
    skipped: 'Upload saved; no map was generated for this revision.',
    not_requested: 'No map generation requested for this revision.',
};

/**
 * Stable DOM hooks: data-geojson-message, data-geojson-error, and
 * data-geojson-artifact identify status text. API values always use textContent.
 */
export function renderGeoJSONStatus(root, data) {
    root.querySelector('[data-geojson-message]').textContent = STATE_MESSAGES[data.state];
    const error = root.querySelector('[data-geojson-error]');
    error.textContent = typeof data.error === 'string' ? data.error : '';
    error.hidden = !error.textContent;
    const artifact = root.querySelector('[data-geojson-artifact]');
    if (!data.geojson_commit_sha) {
        artifact.textContent = 'No map is currently available.';
    } else if (data.source_commit_sha && data.source_commit_sha !== data.geojson_commit_sha) {
        artifact.textContent = `The available map is from an earlier revision (${data.geojson_commit_sha}).`;
    } else {
        artifact.textContent = `Available map revision: ${data.geojson_commit_sha}.`;
    }
}

export async function init(context) {
    const root = document.getElementById('project-geojson-status');
    if (!root) return;
    const endpoint = new URL(context.endpoint, window.location.href);
    if (endpoint.origin !== window.location.origin) throw new Error('Invalid map status endpoint');
    let active = true;
    let pageActive = true;
    let timer = null;
    let request = null;
    let retry = false;

    function stop() {
        window.clearTimeout(timer);
        timer = null;
    }

    function schedule() {
        stop();
        if (active && pageActive && !document.hidden) {
            timer = window.setTimeout(refresh, retry ? RETRY_INTERVAL_MS : POLL_INTERVAL_MS);
        }
    }

    async function refresh() {
        if (!active || !pageActive || document.hidden || request) return;
        stop();
        const controller = new AbortController();
        request = controller;
        let timedOut = false;
        const timeout = window.setTimeout(() => {
            timedOut = true;
            controller.abort();
        }, REQUEST_TIMEOUT_MS);
        root.setAttribute('aria-busy', 'true');
        try {
            const response = await fetch(endpoint.href, {
                credentials: 'same-origin',
                headers: { Accept: 'application/json' },
                signal: controller.signal,
            });
            if (!response.ok) throw new Error('Map status unavailable');
            const payload = await response.json();
            if (controller.signal.aborted) return;
            if (!Object.hasOwn(STATE_MESSAGES, payload?.state)) {
                throw new Error('Invalid map status');
            }
            renderGeoJSONStatus(root, payload);
            active = ACTIVE_STATES.has(payload.state);
            retry = false;
        } catch {
            if (!controller.signal.aborted || timedOut) {
                root.querySelector('[data-geojson-message]').textContent = 'Map status is temporarily unavailable. Retrying shortly.';
                retry = true;
            }
        } finally {
            window.clearTimeout(timeout);
            if (request === controller) {
                request = null;
                root.setAttribute('aria-busy', 'false');
                schedule();
            }
        }
    }

    function cancelRequest() {
        request?.abort();
        request = null;
        root.setAttribute('aria-busy', 'false');
    }

    function onVisibility() {
        stop();
        if (document.hidden) cancelRequest();
        else if (retry) schedule();
        else void refresh();
    }

    function onPageHide() {
        pageActive = false;
        stop();
        cancelRequest();
    }

    function onPageShow() {
        pageActive = true;
        onVisibility();
    }

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pagehide', onPageHide);
    window.addEventListener('pageshow', onPageShow);
    await refresh();
    return () => {
        onPageHide();
        document.removeEventListener('visibilitychange', onVisibility);
        window.removeEventListener('pagehide', onPageHide);
        window.removeEventListener('pageshow', onPageShow);
    };
}

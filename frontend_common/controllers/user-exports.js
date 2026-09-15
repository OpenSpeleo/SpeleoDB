const POLL_INTERVAL_MS = 5000;
const MAX_TIMER_DELAY_MS = 2 ** 31 - 1;
const ACTIVE_STATES = new Set(['queued', 'running', 'retry_wait']);
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const STATE_LABELS = {
    queued: 'Queued',
    running: 'Generating export',
    retry_wait: 'Waiting to retry',
    ready: 'Ready to download',
    partial: 'Ready with omissions',
    failed: 'Export failed',
    cancelled: 'Export cancelled',
};
const STATE_CLASSES = {
    queued: 'exports-badge-active',
    running: 'exports-badge-active',
    retry_wait: 'exports-badge-active',
    ready: 'exports-badge-ready',
    partial: 'exports-badge-warning',
    failed: 'exports-badge-failed',
};
const SIZE_UNITS = ['bytes', 'KB', 'MB', 'GB', 'TB'];
const SIZE_UNIT_BASE = 1000;
const ICON_PATHS = {
    archive: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M10 12h4 M10 16h4',
    download: 'M12 3v12m-4-4 4 4 4-4 M5 16v4a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4',
    retry: 'M3 10a9 9 0 1 1 2 8 M3 4v6h6',
};

function element(tag, text, className = '') {
    const node = document.createElement(tag);
    node.textContent = text;
    node.className = className;
    return node;
}

function dateLabel(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Unknown date' : date.toLocaleString();
}

function sizeLabel(value) {
    const bytes = Number(value);
    if (value == null || !Number.isFinite(bytes) || bytes < 0) return 'Size unavailable';
    const unit = bytes > 0 ? Math.min(Math.floor(Math.log(bytes) / Math.log(SIZE_UNIT_BASE)), SIZE_UNITS.length - 1) : 0;
    const index = Math.max(0, unit);
    return `${(bytes / SIZE_UNIT_BASE ** index).toLocaleString(undefined, { maximumFractionDigits: 1 })} ${SIZE_UNITS[index]}`;
}

function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    for (const [attribute, value] of Object.entries({
        class: 'exports-icon', viewBox: '0 0 24 24', fill: 'none',
        stroke: 'currentColor', 'stroke-width': '1.6', 'stroke-linecap': 'round',
        'stroke-linejoin': 'round', 'aria-hidden': 'true',
    })) svg.setAttribute(attribute, value);
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', ICON_PATHS[name]);
    svg.append(path);
    return svg;
}

function action(tag, label, iconName, className) {
    const control = element(tag, '', `exports-button ${className}`);
    control.append(icon(iconName), element('span', label));
    return control;
}

function omissionLabel(omission) {
    if (typeof omission === 'string') return omission;
    if (!omission || typeof omission !== 'object') return 'An item could not be included.';
    return [omission.category, omission.name, omission.reason || omission.error]
        .filter(value => typeof value === 'string' && value.length > 0).join(': ')
        || 'An item could not be included.';
}

export function requestedExportId(search) {
    const value = new URLSearchParams(search).get('export');
    return value && UUID_PATTERN.test(value) ? value : null;
}

async function responseData(response) {
    const data = await response.json();
    if (!response.ok) {
        const error = new Error(data.detail || 'Unable to load exports. Please try again.');
        error.status = response.status;
        throw error;
    }
    return data;
}

/** Expiry can remove the last row of a later page; fall back once to page one. */
export async function loadExportPage(url, firstPageUrl, options) {
    try {
        return { url, data: await fetch(url, options).then(responseData) };
    } catch (error) {
        if (error.status !== 404 || url === firstPageUrl) throw error;
        return { url: firstPageUrl, data: await fetch(firstPageUrl, options).then(responseData) };
    }
}

/** Keep one visible card per export, including links outside the current page. */
export function mergeExportJobs(jobs, linkedJob = null, now = Date.now()) {
    const merged = new Map(jobs.map(job => [String(job.id).toLowerCase(), job]));
    if (linkedJob) {
        const id = String(linkedJob.id).toLowerCase();
        const pageJob = merged.get(id);
        // The two requests may observe different moments during a retry.
        const pageIsNewer = new Date(pageJob?.updated_at).getTime() > new Date(linkedJob.updated_at).getTime();
        if (!pageIsNewer) merged.set(id, linkedJob);
    }
    return [...merged.values()].filter(job => ACTIVE_STATES.has(job.state) || (
        !job.expired
        && !job.artifact?.deleted_at
        && !(Date.parse(job.artifact?.expires_at) <= now)
    ));
}

/** Refresh active work regularly and ready downloads when their availability ends. */
export function exportRefreshDelay(jobs, active = false, now = Date.now()) {
    let delay = active ? POLL_INTERVAL_MS : Infinity;
    for (const job of jobs) {
        if (ACTIVE_STATES.has(job.state)) continue;
        const expiresAt = Date.parse(job.artifact?.expires_at);
        if (Number.isFinite(expiresAt) && expiresAt > now) {
            delay = Math.min(delay, expiresAt - now);
        }
    }
    return Number.isFinite(delay) ? Math.min(MAX_TIMER_DELAY_MS, Math.max(1, delay)) : null;
}

/**
 * Stable DOM contract: [data-export-id] identifies a history card;
 * [data-export-retry] identifies its retry control. Styles use classes only.
 * All API strings are assigned through textContent.
 */
export function renderExportHistory(container, jobs, { endpoint, busy = false, linkedJob = null, focusId = null, now = Date.now() } = {}) {
    const visibleJobs = mergeExportJobs(jobs, linkedJob, now);
    const active = visibleJobs.some(job => ACTIVE_STATES.has(job.state));
    const previousFocus = document.activeElement;
    const previousCard = previousFocus?.closest('[data-export-id]');
    const previousId = container.contains(previousCard) ? previousCard.dataset.exportId.toLowerCase() : null;
    const previousControl = previousFocus?.matches('[data-export-retry]')
        ? '[data-export-retry]' : previousFocus?.matches('a') ? 'a' : null;
    let focusTarget = null;
    let retainedFocus = null;
    container.replaceChildren();
    if (!visibleJobs.length) {
        const empty = element('div', '', 'exports-empty');
        const symbol = element('div', '', 'exports-empty-icon');
        symbol.append(icon('archive'));
        empty.append(symbol, element('h4', 'No current exports'));
        empty.append(element('p', 'Generate an export above. Your archive will appear here when it’s ready to download.'));
        container.append(empty);
        return false;
    }
    for (const job of visibleJobs) {
        const card = element('article', '', 'exports-card');
        card.dataset.exportId = String(job.id);
        if (focusId && String(job.id).toLowerCase() === focusId.toLowerCase()) {
            card.tabIndex = -1;
            focusTarget = card;
        }
        const main = element('div', '', 'exports-card-main');
        const symbol = element('div', '', 'exports-file-icon');
        symbol.append(icon('archive'));
        const body = element('div', '', 'exports-card-body');
        const heading = element('div', '', 'exports-card-heading');
        heading.append(element('h4', 'Data export'), element('span',
            STATE_LABELS[job.state] || 'Export status unavailable',
            `exports-badge ${STATE_CLASSES[job.state] || ''}`));
        body.append(heading, element('p', `Requested ${dateLabel(job.created_at)}`, 'exports-card-meta'));
        if (ACTIVE_STATES.has(job.state)) {
            body.append(element('p', 'An email will be sent when ready to download.', 'exports-card-description'));
        } else if (job.artifact) {
            body.append(element('p', `${sizeLabel(job.artifact.size_bytes)} · Expires ${dateLabel(job.artifact.expires_at)}`, 'exports-card-meta'));
        }
        main.append(symbol, body);
        card.append(main);
        if (job.state === 'partial') {
            const notice = element('div', '', 'exports-card-notice');
            notice.append(element('p', 'Some files could not be included. Review these omissions before relying on this backup.'));
            const omissions = Array.isArray(job.summary?.omissions) ? job.summary.omissions : [];
            if (omissions.length) {
                const list = element('ul');
                omissions.forEach(omission => list.append(element('li', omissionLabel(omission))));
                notice.append(list);
            }
            notice.append(element('p', 'The ZIP includes the full list in manifest.json.', 'exports-card-meta'));
            card.append(notice);
        }
        if (job.state === 'failed') {
            body.append(element('p', 'The export could not be completed. Retry to take a fresh snapshot of your accessible data.', 'exports-card-description'));
        }
        if (job.notification_state === 'failed') {
            card.append(element('p', 'The notification email could not be delivered. You can follow the export here.', 'exports-card-notice'));
        }
        const actions = element('div', '', 'exports-card-actions');
        if (UUID_PATTERN.test(job.id)) {
            if (job.download_url && !job.expired && ['ready', 'partial'].includes(job.state)) {
                const link = action('a', 'Download ZIP', 'download', 'exports-button-download');
                // Construct the owned route; never trust an API-provided href.
                link.href = `${endpoint}${job.id}/download/`;
                actions.append(link);
            }
            if (job.state === 'failed') {
                const retry = action('button', 'Retry export', 'retry', 'exports-button-secondary');
                retry.type = 'button';
                retry.dataset.exportRetry = job.id;
                retry.disabled = busy || active;
                actions.append(retry);
            }
        }
        if (actions.childElementCount) main.append(actions);
        if (String(job.id).toLowerCase() === previousId) {
            if (previousControl) retainedFocus = card.querySelector(previousControl);
            else if (previousFocus === previousCard) {
                card.tabIndex = -1;
                retainedFocus = card;
            }
        }
        container.append(card);
    }
    // Native focus also scrolls the linked card into view without another panel.
    if (focusTarget) focusTarget.focus();
    else retainedFocus?.focus({ preventScroll: true });
    return Boolean(focusTarget);
}

export async function init(context) {
    const root = document.getElementById('user-exports');
    if (!root) return;
    const endpoint = new URL(context.endpoint, window.location.href);
    if (endpoint.origin !== window.location.origin) throw new Error('Invalid export endpoint');
    const endpointPath = endpoint.pathname;
    const form = root.querySelector('#export-request-form');
    const create = root.querySelector('#export-create');
    const createLabel = root.querySelector('#export-create-label');
    const history = root.querySelector('#export-history');
    const message = root.querySelector('#export-message');
    const previous = root.querySelector('#export-previous');
    const next = root.querySelector('#export-next');
    const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]').value;
    let currentUrl = endpoint.href;
    let previousUrl = null;
    let nextUrl = null;
    let jobs = [];
    let linkedId = requestedExportId(window.location.search);
    let linkedJob = null;
    let focusLinkedExport = Boolean(linkedId);
    let active = false;
    let mutationPending = false;
    let pageActive = true;
    let timer = null;
    let requestController = null;

    function safePageUrl(value) {
        if (!value) return null;
        const url = new URL(value, endpoint);
        return url.origin === endpoint.origin && url.pathname === endpointPath ? url.href : null;
    }

    function redraw(now = Date.now()) {
        create.disabled = mutationPending || active;
        createLabel.textContent = mutationPending ? 'Requesting export…' : 'Generate export';
        create.setAttribute('aria-busy', String(mutationPending));
        const focused = renderExportHistory(history, jobs, {
            endpoint: endpointPath,
            busy: mutationPending || active,
            linkedJob,
            focusId: focusLinkedExport ? linkedId : null,
            now,
        });
        if (focused) focusLinkedExport = false;
        previous.hidden = !previousUrl;
        next.hidden = !nextUrl;
        previous.disabled = mutationPending;
        next.disabled = mutationPending;
    }

    function stopPolling() {
        window.clearTimeout(timer);
        timer = null;
    }

    function schedule() {
        stopPolling();
        const now = Date.now();
        redraw(now);
        if (!mutationPending && pageActive && !document.hidden) {
            const delay = exportRefreshDelay(mergeExportJobs(jobs, linkedJob, now), active, now);
            if (delay !== null) {
                timer = window.setTimeout(() => {
                    // Remove newly expired cards before waiting for the network.
                    redraw();
                    void refresh();
                }, delay);
            }
        }
    }

    async function refresh() {
        stopPolling();
        requestController?.abort();
        const controller = new AbortController();
        requestController = controller;
        history.setAttribute('aria-busy', 'true');
        try {
            const options = { credentials: 'same-origin', signal: controller.signal };
            const [pageResult, linkedResult] = await Promise.allSettled([
                loadExportPage(currentUrl, endpoint.href, options),
                linkedId ? fetch(`${endpoint.href}${linkedId}/`, options).then(responseData) : Promise.resolve(null),
            ]);
            if (controller.signal.aborted) return;
            let failedLoad = false;
            if (pageResult.status === 'fulfilled') {
                const { url, data } = pageResult.value;
                currentUrl = url;
                jobs = data.results;
                previousUrl = safePageUrl(data.previous);
                nextUrl = safePageUrl(data.next);
            } else {
                message.textContent = pageResult.reason.message;
                failedLoad = true;
            }
            if (linkedResult.status === 'fulfilled') {
                linkedJob = linkedResult.value;
            } else {
                linkedJob = null;
                message.textContent = linkedResult.reason.status === 404
                    ? 'This export could not be found.'
                    : linkedResult.reason.message;
                failedLoad ||= !linkedResult.reason.status || linkedResult.reason.status >= 500;
            }
            const visibleJobs = mergeExportJobs(jobs, linkedJob);
            if (linkedJob && !visibleJobs.some(job => String(job.id).toLowerCase() === linkedId.toLowerCase())) {
                message.textContent = 'This export has expired. Generate a new export.';
            }
            active = failedLoad || visibleJobs.some(job => ACTIVE_STATES.has(job.state));
        } catch (error) {
            if (error.name !== 'AbortError') {
                message.textContent = error.message;
                // Also retry the initial load, when no job states are known yet.
                active = true;
            }
        } finally {
            if (requestController === controller) {
                history.setAttribute('aria-busy', 'false');
                schedule();
            }
        }
    }

    async function submit(url) {
        if (mutationPending) return;
        mutationPending = true;
        requestController?.abort();
        stopPolling();
        redraw();
        try {
            const requested = await fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': csrfToken, 'Accept': 'application/json' },
            }).then(responseData);
            if (UUID_PATTERN.test(requested.id)) {
                linkedId = requested.id;
                linkedJob = requested;
                focusLinkedExport = true;
                const pageUrl = new URL(window.location.href);
                pageUrl.searchParams.set('export', linkedId);
                window.history.replaceState(null, '', pageUrl);
            }
            message.textContent = 'Your export is queued. We will email you when it is ready.';
            currentUrl = endpoint.href;
        } catch (error) {
            message.textContent = error.message;
        } finally {
            mutationPending = false;
            await refresh();
        }
    }

    function onSubmit(event) {
        event.preventDefault();
        if (!active) void submit(endpoint.href);
    }
    function onRetry(event) {
        const button = event.target instanceof Element ? event.target.closest('[data-export-retry]') : null;
        if (button && !button.disabled && UUID_PATTERN.test(button.dataset.exportRetry)) {
            void submit(`${endpointPath}${button.dataset.exportRetry}/retry/`);
        }
    }
    function onPrevious() {
        if (previousUrl) { currentUrl = previousUrl; void refresh(); }
    }
    function onNext() {
        if (nextUrl) { currentUrl = nextUrl; void refresh(); }
    }
    function onVisibility() {
        stopPolling();
        if (!document.hidden) void refresh();
    }
    function onPageHide() {
        pageActive = false;
        stopPolling();
        requestController?.abort();
    }
    function onPageShow() {
        pageActive = true;
        onVisibility();
    }
    form.addEventListener('submit', onSubmit);
    history.addEventListener('click', onRetry);
    previous.addEventListener('click', onPrevious);
    next.addEventListener('click', onNext);
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pagehide', onPageHide);
    window.addEventListener('pageshow', onPageShow);
    await refresh();
}
